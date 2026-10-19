import asyncio
import json
import logging
import uuid
from typing import Any, Dict, Optional
from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse
import redis.asyncio as redis
from app.services.device_service import normalize_device_id

router = APIRouter(prefix="/api/v1/agent", tags=["agent"])
logger = logging.getLogger("remote_support.agent_proxy")


def get_redis(request: Request) -> redis.Redis:
    return request.app.state.redis


@router.get("/health")
async def agent_gateway_health():
    """
    Health check for the agent gateway.
    Never connects to localhost/127.0.0.1 to avoid executing actions on the local server machine.
    """
    return {
        "status": "ok",
        "gateway": "remote_dispatch",
        "mode": "device_targeted",
    }


@router.get("/{device_id}/health")
async def device_agent_health(device_id: str, request: Request):
    """
    Checks the real online status of the native companion agent on the specified remote device.
    """
    norm_id = normalize_device_id(device_id)
    r = get_redis(request)
    online = await r.exists(f"device:{norm_id}:agent_online")
    raw_info = await r.hgetall(f"device:{norm_id}:agent_info")
    info = {}
    for k, v in (raw_info or {}).items():
        try:
            info[k] = json.loads(v)
        except Exception:
            info[k] = v

    return {
        "device_id": norm_id,
        "agent_online": bool(online),
        "info": info,
    }


@router.post("/{device_id}/{action:path}")
async def dispatch_to_remote_agent(device_id: str, action: str, request: Request):
    """
    Dispatches an action to the remote connected laptop via the device's persistent agent channel.
    Guarantees no local-machine execution.
    """
    norm_id = normalize_device_id(device_id)
    r = get_redis(request)

    clean_action = action.strip("/").replace("/", "_")
    try:
        body = await request.json()
    except Exception:
        body = {}

    req_id = f"req_{uuid.uuid4().hex[:10]}"
    payload = {
        "type": clean_action,
        "req_id": req_id,
        **body,
    }

    # Subscribe to session channel to wait for agent's reply
    pubsub = r.pubsub()
    session_channel = f"channel:session:{norm_id}"
    await pubsub.subscribe(session_channel)

    try:
        # Publish request to the remote agent
        await r.publish(f"channel:agent:{norm_id}", json.dumps(payload))

        # Wait for reply matching req_id
        async def wait_for_reply():
            async for msg in pubsub.listen():
                if msg["type"] != "message":
                    continue
                try:
                    data = json.loads(msg["data"])
                    inner = data.get("data") if (isinstance(data, dict) and "data" in data) else data
                    if isinstance(inner, dict) and inner.get("req_id") == req_id:
                        return inner
                except Exception:
                    pass
            return None

        reply = await asyncio.wait_for(wait_for_reply(), timeout=6.0)
        if reply:
            return JSONResponse(status_code=200, content=reply)
        return JSONResponse(
            status_code=504,
            content={"error": f"Remote host agent for {norm_id} did not respond.", "status": "timeout"},
        )
    except asyncio.TimeoutError:
        return JSONResponse(
            status_code=504,
            content={"error": f"Remote host agent for {norm_id} timed out.", "status": "timeout"},
        )
    except Exception as e:
        logger.exception(f"Error dispatching to agent {norm_id}: {e}")
        return JSONResponse(
            status_code=502,
            content={"error": str(e), "status": "error"},
        )
    finally:
        await pubsub.unsubscribe(session_channel)
        await pubsub.aclose()
