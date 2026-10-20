import asyncio
import json
import logging
import secrets
import uuid
from typing import Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import redis.asyncio as redis

from app.database import async_session_factory
from app.services.device_service import normalize_device_id, verify_agent_token, verify_device_token
from app.services.presence_service import set_device_online, set_device_offline
from app.services.session_service import issue_viewer_token, revoke_viewer_token

logger = logging.getLogger(__name__)
router = APIRouter(tags=["signaling"])

PEER_TTL_SECONDS = 60
AGENT_AUTH_TIMEOUT_SECONDS = 10
SIGNAL_TYPES = {
    "offer": ("host", "client"),
    "answer": ("client", "host"),
    "ice_restart_request": ("client", "host"),
    "permission_denied": ("host", "client"),
    "session_ended": ("host", "client"),
}
# Remote input events. These are only relayed while the host has granted control to the client.
INPUT_EVENT_TYPES = {
    "mousemove", "mousedown", "mouseup", "click", "dblclick", "contextmenu", "scroll",
    "keydown", "keyup",
}


def normalize_session_code(val: str) -> str:
    cleaned = val.strip()
    return normalize_device_id(cleaned)



# ═════════════════════════════════════════════════════════════
# 1. Device Push Notification Channel: /ws/device/{device_id}
# ═════════════════════════════════════════════════════════════

@router.websocket("/ws/device/{device_id}")
async def device_notification_endpoint(websocket: WebSocket, device_id: str) -> None:
    redis_client: redis.Redis = websocket.app.state.redis
    norm_device_id = normalize_device_id(device_id)

    await websocket.accept()

    # This channel delivers connection requests (with their request ids) and marks the device
    # online, so only the device itself may open it. Its first message carries the device token.
    try:
        first = json.loads(await asyncio.wait_for(websocket.receive_text(), timeout=AGENT_AUTH_TIMEOUT_SECONDS))
        token = str(first.get("token", "") or "") if isinstance(first, dict) and first.get("type") == "auth" else ""
        async with async_session_factory() as db:
            authenticated = bool(token) and await verify_device_token(db, norm_device_id, token)
    except Exception as e:
        logger.debug(f"Device push auth handshake failed for {norm_device_id}: {e}")
        authenticated = False
    if not authenticated:
        logger.warning(f"Rejected unauthenticated push channel for device: {norm_device_id}")
        try:
            await websocket.send_json({"type": "error", "message": "Device authentication failed."})
            await websocket.close(code=4401, reason="Invalid device token")
        except Exception:
            pass
        return
    await websocket.send_json({"type": "authenticated", "device_id": norm_device_id})

    channel_name = f"channel:device:{norm_device_id}"
    pubsub = redis_client.pubsub()
    await pubsub.subscribe(channel_name)
    logger.info(f"Device connected to push channel: {norm_device_id}")

    # Mark device online
    await set_device_online(redis_client, norm_device_id, ttl=45)

    # Immediately deliver any active pending request for this device
    pending_request = await redis_client.get(f"device:{norm_device_id}:pending_request")
    if pending_request:
        try:
            req_data = json.loads(pending_request)
            await websocket.send_json(req_data)
            logger.info(f"Delivered pending connection request to push channel: {norm_device_id}")
        except Exception as err:
            logger.warning(f"Failed to deliver pending request to {norm_device_id}: {err}")

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
# 2. Native Companion Agent Channel: /ws/agent/{device_id}
# ═════════════════════════════════════════════════════════════

@router.websocket("/ws/agent/{device_id}")
async def agent_companion_endpoint(websocket: WebSocket, device_id: str) -> None:
    redis_client: redis.Redis = websocket.app.state.redis
    norm_device_id = normalize_device_id(device_id)
    raw_device_id = device_id.strip()

    await websocket.accept()

    # The agent receives the controller's input and the host's terminal and file requests, so
    # it must prove it belongs to this device before anything is routed to it. Its first
    # message is agent_info carrying the agent token from /api/v1/devices/register.
    try:
        first = json.loads(await asyncio.wait_for(websocket.receive_text(), timeout=AGENT_AUTH_TIMEOUT_SECONDS))
        agent_token = str(first.pop("token", "") or "") if isinstance(first, dict) else ""
        async with async_session_factory() as db:
            authenticated = await verify_agent_token(db, norm_device_id, agent_token)
    except Exception as e:
        logger.debug(f"Agent auth handshake failed for {norm_device_id}: {e}")
        authenticated = False
    if not authenticated:
        logger.warning(f"Rejected unauthenticated companion agent for device: {norm_device_id}")
        try:
            await websocket.send_json({"type": "error", "message": "Agent authentication failed."})
            await websocket.close(code=4401, reason="Invalid agent token")
        except Exception:
            pass
        return

    agent_channel_norm = f"channel:agent:{norm_device_id}"
    agent_channel_raw = f"channel:agent:{raw_device_id}"
    pubsub = redis_client.pubsub()
    await pubsub.subscribe(agent_channel_norm)
    if agent_channel_raw != agent_channel_norm:
        await pubsub.subscribe(agent_channel_raw)
    logger.info(f"Native companion agent connected for device: {norm_device_id}")

    # Set agent presence in Redis
    await redis_client.set(f"device:{norm_device_id}:agent_online", "1", ex=60)
    if raw_device_id != norm_device_id:
        await redis_client.set(f"device:{raw_device_id}:agent_online", "1", ex=60)
    await websocket.send_json({"type": "agent_connected", "device_id": norm_device_id})

    async def keep_presence():
        # Presence lasts as long as this socket, so agents need not send app-level heartbeats
        try:
            while True:
                await asyncio.sleep(20)
                await redis_client.set(f"device:{norm_device_id}:agent_online", "1", ex=60)
                if raw_device_id != norm_device_id:
                    await redis_client.set(f"device:{raw_device_id}:agent_online", "1", ex=60)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.debug(f"Agent presence refresh failed for {norm_device_id}: {e}")

    presence_task = asyncio.create_task(keep_presence())

    async def forward_to_agent():
        try:
            async for message in pubsub.listen():
                if message["type"] != "message":
                    continue
                data = json.loads(message["data"])
                await websocket.send_json(data)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.debug(f"Agent listener exception for {norm_device_id}: {e}")

    task = asyncio.create_task(forward_to_agent())

    async def handle_agent_message(data: dict) -> None:
        msg_type = data.get("type")

        if msg_type in ("ping", "heartbeat"):
            await redis_client.set(f"device:{norm_device_id}:agent_online", "1", ex=60)
            await websocket.send_json({"type": "pong"})
        elif msg_type == "agent_info":
            # agent_info is readable via /system_info, so the credential must never be stored
            data.pop("token", None)
            await redis_client.set(f"device:{norm_device_id}:agent_online", "1", ex=60)
            flat_info = {}
            for k, v in data.items():
                flat_info[k] = json.dumps(v) if isinstance(v, (list, dict, bool)) else str(v)
            await redis_client.hset(f"device:{norm_device_id}:agent_info", mapping=flat_info)
            # Agent traffic answers the host's requests; the controller never needs it.
            session_payload = json.dumps({
                "connection_id": "agent",
                "sender_role": "agent",
                "target_role": "host",
                "data": {"type": "agent_info", **data},
            })
            await redis_client.publish(f"channel:session:{norm_device_id}", session_payload)
            if raw_device_id != norm_device_id:
                await redis_client.publish(f"channel:session:{raw_device_id}", session_payload)
        elif msg_type in ("reply", "control_granted", "control_released", "control_revoked"):
            session_payload = json.dumps({
                "connection_id": "agent",
                "sender_role": "agent",
                "target_role": "host",
                "data": data,
            })
            await redis_client.publish(f"channel:session:{norm_device_id}", session_payload)
            if raw_device_id != norm_device_id:
                await redis_client.publish(f"channel:session:{raw_device_id}", session_payload)

    try:
        # The handshake message is the agent's first agent_info
        await handle_agent_message(first)
        while True:
            await handle_agent_message(json.loads(await websocket.receive_text()))
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.debug(f"Agent WS disconnected for {norm_device_id}: {e}")
    finally:
        task.cancel()
        presence_task.cancel()
        await redis_client.delete(f"device:{norm_device_id}:agent_online")
        if raw_device_id != norm_device_id:
            await redis_client.delete(f"device:{raw_device_id}:agent_online")
        await pubsub.unsubscribe(agent_channel_norm)
        if agent_channel_raw != agent_channel_norm:
            await pubsub.unsubscribe(agent_channel_raw)
        await pubsub.aclose()
        logger.info(f"Native companion agent disconnected for device: {norm_device_id}")


# ═════════════════════════════════════════════════════════════
# 3. WebRTC Session Signaling Channel: /ws/{session_id}
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
        is_dev = await redis_client.exists(f"device:{code}:presence") or await redis_client.exists(f"presence:device:{code}")
        if not is_dev:
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
    norm_code = normalize_device_id(code)
    channel_name = f"channel:session:{code}"
    pubsub = redis_client.pubsub()
    await pubsub.subscribe(channel_name)
    if norm_code != code:
        await pubsub.subscribe(f"channel:session:{norm_code}")
    logger.info(f"WebSocket connected for session {code} (norm: {norm_code}) [{connection_id}]")

    async def send_error(msg: str) -> None:
        await websocket.send_json({"type": "error", "message": msg})

    async def publish_event(sender_role: str, data: dict, target_role: Optional[str]) -> None:
        payload = json.dumps({
            "connection_id": connection_id,
            "sender_role": sender_role,
            "target_role": target_role,
            "data": data,
        })
        await redis_client.publish(channel_name, payload)
        if norm_code != code:
            await redis_client.publish(f"channel:session:{norm_code}", payload)

    # Control state: the host is the only authority. This key holds the connection id of the
    # client the host granted control to; input is relayed only from that connection.
    control_key = f"session:{code}:control"

    async def publish_to_agent(event: dict) -> None:
        raw = json.dumps(event)
        await redis_client.publish(f"channel:agent:{norm_code}", raw)
        if norm_code != code:
            await redis_client.publish(f"channel:agent:{code}", raw)

    async def holds_control() -> bool:
        return role == "client" and await redis_client.get(control_key) == connection_id

    async def end_control(notify_host: bool = False) -> None:
        await redis_client.delete(control_key)
        # The agent stops injecting and releases any held buttons/keys
        await publish_to_agent({"type": "release_control"})
        if notify_host:
            await publish_event("client", {"type": "release_control"}, "host")

    async def route_control_event(message_type: str, event: dict) -> None:
        """Route a session-control or input event sent by a peer.

        `agent_control` is bound for the companion agent, `control_event` for the host peer
        (data-channel fallback). Each event goes to exactly one place so input is never
        injected twice, and input only flows while the sending client holds control.
        """
        event_type = event.get("type")
        if role == "client":
            if event_type == "take_control":
                # Only the host can grant control; the agent is armed once it does
                await publish_event(role, event, "host")
            elif event_type == "release_control":
                await end_control()
                await publish_event(role, event, "host")
            elif event_type in INPUT_EVENT_TYPES and not await holds_control():
                return
            elif message_type == "control_event":
                await publish_event(role, event, "host")
            elif event_type in INPUT_EVENT_TYPES:
                await publish_to_agent(event)
            # Any other agent request from a client (terminal, filesystem, clipboard, ...) is
            # dropped: those are issued by the host on the controller's behalf.
        elif message_type == "agent_control" and event_type not in INPUT_EVENT_TYPES:
            # Host-originated agent requests (terminal, filesystem, clipboard, info)
            await publish_to_agent(event)

    async def listen_for_peer() -> None:
        try:
            async for message in pubsub.listen():
                try:
                    if message["type"] != "message":
                        continue
                    payload = json.loads(message["data"])
                    if payload.get("connection_id") == connection_id:
                        continue
                    if payload.get("target_connection") not in (None, connection_id):
                        continue
                    if role and payload.get("target_role") in (None, role):
                        msg_to_send = payload.get("data") if (isinstance(payload, dict) and "data" in payload) else payload
                        await websocket.send_json(msg_to_send)
                except Exception as inner_e:
                    logger.warning(f"Error handling pubsub message in session {code}: {inner_e}")
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.exception(f"Redis listener failed for session {code}")

    async def verify_host_token(room: str, session_data: dict, token: str) -> bool:
        if not token:
            return False
        expected_host = session_data.get("host_token", "")
        if expected_host and secrets.compare_digest(expected_host, token):
            return True
        device_ids = {room, session_data.get("device_id") or room}
        try:
            async with async_session_factory() as db:
                for device_id in device_ids:
                    if await verify_device_token(db, device_id, token):
                        await redis_client.hset(f"session:{room}", "host_token", token)
                        return True
        except Exception as auth_err:
            logger.warning(f"DB credential verification failed for host {room}: {auth_err}")
        return False

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
                    if await holds_control():
                        await redis_client.expire(control_key, PEER_TTL_SECONDS)
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
                    # Only the device itself may host: it must present the room's host token
                    # (set by device register/heartbeat or legacy session create) or a device
                    # token that verifies against the database. The controller's session token
                    # is not accepted.
                    token = data.get("host_token") or ""
                    if not await verify_host_token(code, session_data, token):
                        await send_error("Host authentication failed.")
                        await websocket.close(code=4403, reason="Invalid host token")
                        break
                else:
                    # requested_role == "client"
                    # Notify host via device push channel that a client is waiting in room
                    caller_id = data.get("client_device_id") or "Remote Client"
                    caller_name = data.get("caller_name") or "Remote Controller"
                    await redis_client.hset(
                        f"session:{code}:client_info",
                        mapping={"caller_device_id": caller_id, "caller_name": caller_name},
                    )
                    await redis_client.expire(f"session:{code}:client_info", 300)

                    waiting_payload = json.dumps({
                        "type": "client_waiting",
                        "session_code": code,
                        "connection_id": connection_id,
                        "request_id": f"direct-{code}",
                        "caller_device_id": caller_id,
                        "caller_name": caller_name,
                    })
                    # Cache waiting payload as pending request for late-joining hosts
                    await redis_client.set(f"device:{code}:pending_request", waiting_payload, ex=120)
                    await redis_client.set(f"session:{code}:pending_request", waiting_payload, ex=120)

                    await redis_client.publish(f"channel:device:{code}", waiting_payload)
                    await redis_client.publish(f"channel:session:{code}", waiting_payload)

                # Set or update the active peer connection for this role in Redis
                await redis_client.set(
                    peer_key(requested_role),
                    connection_id,
                    ex=PEER_TTL_SECONDS,
                )

                if requested_role == "client":
                    # A new controller must be approved again before it can read device metadata
                    await revoke_viewer_token(redis_client, norm_code)
                    holder = await redis_client.get(control_key)
                    if holder and holder != connection_id:
                        # Control belongs to a previous controller connection; the new one must ask again
                        await end_control(notify_host=True)

                role = requested_role
                other_role = "client" if role == "host" else "host"
                await websocket.send_json({"type": "registered", "role": role})

                # If host just registered, check for any pending request or waiting client
                if role == "host":
                    pending_req = await redis_client.get(f"session:{code}:pending_request") or await redis_client.get(f"device:{code}:pending_request")
                    if pending_req:
                        try:
                            await websocket.send_json(json.loads(pending_req))
                        except Exception:
                            pass

                # Check if other peer is already present in room
                if await redis_client.exists(peer_key(other_role)):
                    if role == "host":
                        c_info = await redis_client.hgetall(f"session:{code}:client_info")
                        c_id = c_info.get("caller_device_id", "Remote Client")
                        c_name = c_info.get("caller_name", "Remote Controller")
                        await websocket.send_json({
                            "type": "peer_joined",
                            "role": "client",
                            "caller_device_id": c_id,
                            "caller_name": c_name,
                        })
                    else:
                        await websocket.send_json({"type": "peer_joined", "role": other_role})
                elif role == "client":
                    # Inform client that signaling room is ready and waiting for host
                    await websocket.send_json({
                        "type": "waiting_for_host",
                        "message": "Waiting for remote host to start stream...",
                    })

                peer_joined_payload = {
                    "type": "peer_joined",
                    "role": role,
                    "caller_device_id": data.get("client_device_id") or "Remote Client",
                    "caller_name": data.get("caller_name") or "Remote Controller",
                }
                await publish_event(
                    role,
                    peer_joined_payload,
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
                if role == "host" and message_type == "offer":
                    # The host sends its offer only once it has approved the waiting controller,
                    # so that controller connection now gets a viewer token for the device's
                    # metadata and SSH bridge. It is delivered to that connection alone.
                    client_connection = await redis_client.get(peer_key("client"))
                    if client_connection:
                        viewer_token = await issue_viewer_token(redis_client, code, norm_code, client_connection)
                        await redis_client.publish(channel_name, json.dumps({
                            "connection_id": connection_id,
                            "sender_role": "host",
                            "target_role": "client",
                            "target_connection": client_connection,
                            "data": {"type": "session_credential", "viewer_token": viewer_token},
                        }))
                    await redis_client.delete(f"device:{code}:pending_request")
                    await redis_client.delete(f"session:{code}:pending_request")
                    await redis_client.delete(f"device:{norm_code}:pending_request")
                    await redis_client.delete(f"session:{norm_code}:pending_request")
            elif message_type == "ice_restart_request":
                target_role = "host"
            elif message_type in ("agent_control", "control_event"):
                if isinstance(data.get("data"), dict):
                    await route_control_event(message_type, data["data"])
                continue
            elif message_type in ("take_control", "release_control"):
                await route_control_event("control_event", data)
                continue
            elif message_type in ("control_granted", "control_released", "control_revoked", "control_denied") and role == "host":
                if message_type == "control_granted":
                    client_connection = await redis_client.get(peer_key("client"))
                    if client_connection:
                        await redis_client.set(control_key, client_connection, ex=PEER_TTL_SECONDS)
                        if data.get("input_route", "agent") == "agent":
                            # Arm the companion agent; it injects input only while armed
                            await publish_to_agent({"type": "take_control"})
                else:
                    await end_control()
                target_role = "client"
            elif message_type in ("system_info", "monitors", "monitor_switched", "quality_changed", "host_stats"):
                # Forward from host to client
                target_role = "client"
            elif message_type in ("chat", "clipboard"):
                # Bidirectional
                target_role = "client" if role == "host" else "host"
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
            if await holds_control():
                await end_control()
            stored_connection = await redis_client.get(peer_key(role))
            if stored_connection == connection_id:
                if role == "host":
                    await end_control()
                    await revoke_viewer_token(redis_client, norm_code)
                else:
                    await revoke_viewer_token(redis_client, norm_code, connection_id)
                await redis_client.delete(peer_key(role))
                other_role = "client" if role == "host" else "host"
                await publish_event(
                    role,
                    {"type": "peer_left", "role": role},
                    other_role,
                )
        await pubsub.unsubscribe(channel_name)
        if norm_code != code:
            await pubsub.unsubscribe(f"channel:session:{norm_code}")
        await pubsub.aclose()
        logger.info(f"WebSocket disconnected for session {code} [{connection_id}]")
