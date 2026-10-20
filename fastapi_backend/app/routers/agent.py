import json
import logging
from fastapi import APIRouter, Request
import redis.asyncio as redis
from app.services.device_service import normalize_device_id

# Read-only presence endpoints. Agent requests (terminal, filesystem) are issued only by the
# authenticated host over its signaling socket; there is deliberately no REST dispatch route.
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
