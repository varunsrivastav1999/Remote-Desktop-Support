import asyncio
import json
import logging
import secrets
import uuid
from typing import Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import redis.asyncio as redis

from app.services.device_service import normalize_device_id
from app.services.presence_service import set_device_online, set_device_offline

logger = logging.getLogger(__name__)
router = APIRouter(tags=["signaling"])

PEER_TTL_SECONDS = 60
SIGNAL_TYPES = {
    "offer": ("host", "client"),
    "answer": ("client", "host"),
    "ice_restart_request": ("client", "host"),
    "permission_denied": ("host", "client"),
    "session_ended": ("host", "client"),
}


def normalize_session_code(val: str) -> str:
    cleaned = val.strip()
    if cleaned.startswith("AG-") or cleaned.startswith("ag-"):
        return normalize_device_id(cleaned)
    digits = "".join(c for c in cleaned if c.isdigit())
    if len(digits) == 9:
        return f"{digits[:3]}-{digits[3:6]}-{digits[6:]}"
    return cleaned


# ═════════════════════════════════════════════════════════════
# 1. Device Push Notification Channel: /ws/device/{device_id}
# ═════════════════════════════════════════════════════════════

@router.websocket("/ws/device/{device_id}")
async def device_notification_endpoint(websocket: WebSocket, device_id: str) -> None:
    redis_client: redis.Redis = websocket.app.state.redis
    norm_device_id = normalize_device_id(device_id)

    await websocket.accept()
    channel_name = f"channel:device:{norm_device_id}"
    pubsub = redis_client.pubsub()
    await pubsub.subscribe(channel_name)
    logger.info(f"Device connected to push channel: {norm_device_id}")

    # Mark device online
    await set_device_online(redis_client, norm_device_id, ttl=45)

    async def listen_for_device_events() -> None:
        try:
            async for message in pubsub.listen():
                if message["type"] != "message":
                    continue
                data = json.loads(message["data"])
                await websocket.send_json(data)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.debug(f"Device listener exception for {norm_device_id}: {e}")

    listener_task = asyncio.create_task(listen_for_device_events())

    try:
        while True:
            text = await websocket.receive_text()
            data = json.loads(text)
            msg_type = data.get("type")

            if msg_type == "ping" or msg_type == "heartbeat":
                await set_device_online(redis_client, norm_device_id, ttl=45)
                await websocket.send_json({"type": "pong"})
            elif msg_type == "network_change":
                # Host detected IP / interface change
                logger.info(f"Device {norm_device_id} reported network change: {data.get('details')}")
                await set_device_online(redis_client, norm_device_id, ttl=45)
                await websocket.send_json({"type": "network_change_acknowledged"})
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.debug(f"Device WS disconnected for {norm_device_id}: {e}")
    finally:
        listener_task.cancel()
        await pubsub.unsubscribe(channel_name)
        await pubsub.aclose()
        logger.info(f"Device disconnected from push channel: {norm_device_id}")


# ═════════════════════════════════════════════════════════════
# 2. WebRTC Session Signaling Channel: /ws/{session_id}
# ═════════════════════════════════════════════════════════════

@router.websocket("/ws/{session_id}")
async def signaling_endpoint(websocket: WebSocket, session_id: str) -> None:
    redis_client: redis.Redis = websocket.app.state.redis
    code = normalize_session_code(session_id)

    # Check if session exists in Redis
    session = await redis_client.hgetall(f"session:{code}")
    if not session:
        # Check if mapped to a device
        alt_code = await redis_client.get(f"device:{code}:session")
        if alt_code:
            code = alt_code
            session = await redis_client.hgetall(f"session:{code}")

    if not session:
        # Check if code is a registered Device ID or create a room for host
        is_dev = await redis_client.exists(f"presence:device:{code}")
        if not is_dev:
            from app.database import async_session_factory
            from app.models.device import Device
            from sqlalchemy import select
            try:
                async with async_session_factory() as db:
                    dev = await db.scalar(select(Device).where(Device.id == code))
                    if dev:
                        is_dev = True
            except Exception as e:
                logger.warning(f"Error checking device {code}: {e}")

        if is_dev or code.startswith("AG-") or len(code) == 11 or len(code) == 14:
            session = {
                "status": "waiting",
                "device_id": code,
                "created_at": "now",
            }
            await redis_client.hset(f"session:{code}", mapping=session)
            await redis_client.expire(f"session:{code}", 86400)
        else:
            await websocket.close(code=4404, reason="Session not found")
            return

    await websocket.accept()
    connection_id = str(uuid.uuid4())
    role: Optional[str] = None
    channel_name = f"channel:session:{code}"
    pubsub = redis_client.pubsub()
    await pubsub.subscribe(channel_name)
    logger.info(f"WebSocket connected for session {code} [{connection_id}]")

    async def send_error(msg: str) -> None:
        await websocket.send_json({"type": "error", "message": msg})

    async def publish_event(sender_role: str, data: dict, target_role: Optional[str]) -> None:
        await redis_client.publish(
            channel_name,
            json.dumps({
                "connection_id": connection_id,
                "sender_role": sender_role,
                "target_role": target_role,
                "data": data,
            }),
        )

    async def listen_for_peer() -> None:
        try:
            async for message in pubsub.listen():
                if message["type"] != "message":
                    continue
                payload = json.loads(message["data"])
                if payload.get("connection_id") == connection_id:
                    continue
                if role and payload.get("target_role") in (None, role):
                    await websocket.send_json(payload["data"])
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.exception(f"Redis listener failed for session {code}")

    listener_task = asyncio.create_task(listen_for_peer())

    peer_key = lambda r: f"session:{code}:peer:{r}"

    try:
        while True:
            text = await websocket.receive_text()
            data = json.loads(text)
            message_type = data.get("type")

            if message_type == "ping":
                if role:
                    await redis_client.expire(peer_key(role), PEER_TTL_SECONDS)
                await websocket.send_json({"type": "pong"})
                continue

            if message_type == "register":
                requested_role = data.get("role")
                if role:
                    await send_error("Peer is already registered.")
                    continue
                if requested_role not in ("host", "client"):
                    await send_error("Role must be host or client.")
                    continue

                session_data = await redis_client.hgetall(f"session:{code}")
                if requested_role == "host":
                    token = data.get("host_token") or data.get("session_token") or ""
                    expected_host = session_data.get("host_token", "")
                    expected_session = session_data.get("session_token", "")
                    valid = False
                    if token and expected_host and secrets.compare_digest(expected_host, token):
                        valid = True
                    elif token and expected_session and secrets.compare_digest(expected_session, token):
                        valid = True

                    if not valid:
                        await send_error("Host authentication failed.")
                        await websocket.close(code=4403, reason="Invalid host token")
                        break
                elif not await redis_client.exists(peer_key("host")):
                    await send_error("The remote desk is offline.")
                    await websocket.close(code=4409, reason="Host offline")
                    break

                claimed = await redis_client.set(
                    peer_key(requested_role),
                    connection_id,
                    ex=PEER_TTL_SECONDS,
                    nx=True,
                )
                if not claimed:
                    # Check if stale connection
                    old_conn = await redis_client.get(peer_key(requested_role))
                    if old_conn != connection_id:
                        await send_error(f"A {requested_role} is already connected.")
                        await websocket.close(code=4409, reason="Peer role in use")
                        break

                role = requested_role
                other_role = "client" if role == "host" else "host"
                await websocket.send_json({"type": "registered", "role": role})

                if await redis_client.exists(peer_key(other_role)):
                    await websocket.send_json({"type": "peer_joined", "role": other_role})

                await publish_event(
                    role,
                    {"type": "peer_joined", "role": role},
                    other_role,
                )
                continue

            if not role:
                await send_error("Register before sending signaling messages.")
                continue

            if message_type == "ice":
                target_role = "client" if role == "host" else "host"
            elif message_type in SIGNAL_TYPES and SIGNAL_TYPES[message_type][0] == role:
                target_role = SIGNAL_TYPES[message_type][1]
            elif message_type == "ice_restart_request":
                target_role = "host"
            else:
                await send_error(f"Message type '{message_type}' is not allowed for role '{role}'.")
                continue

            await publish_event(role, data, target_role)

    except WebSocketDisconnect:
        pass
    except json.JSONDecodeError:
        await send_error("Invalid JSON.")
    except Exception as e:
        logger.exception(f"WebSocket error for session {code}: {e}")
    finally:
        listener_task.cancel()
        if role:
            stored_connection = await redis_client.get(peer_key(role))
            if stored_connection == connection_id:
                await redis_client.delete(peer_key(role))
                other_role = "client" if role == "host" else "host"
                await publish_event(
                    role,
                    {"type": "peer_left", "role": role},
                    other_role,
                )
        await pubsub.unsubscribe(channel_name)
        await pubsub.aclose()
        logger.info(f"WebSocket disconnected for session {code} [{connection_id}]")
