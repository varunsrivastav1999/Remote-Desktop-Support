import logging
from fastapi import APIRouter, Depends, HTTPException, Request, status
import redis.asyncio as redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.routers.devices import bearer_token, read_agent_info
from app.services.device_service import normalize_device_id
from app.services.session_service import verify_device_or_viewer_token

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
async def device_agent_health(
    device_id: str,
    request: Request,
    token: str = Depends(bearer_token),
    db: AsyncSession = Depends(get_db),
):
    """
    Checks the real online status of the native companion agent on the specified remote device.
    It returns the agent's system info, so it needs the device token or the session's viewer token;
    the public /devices/{id}/agent_status reports presence alone.
    """
    norm_id = normalize_device_id(device_id)
    r = get_redis(request)
    if not await verify_device_or_viewer_token(db, r, norm_id, token):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authorized for this device")
    online = await r.exists(f"device:{norm_id}:agent_online")
    info = await read_agent_info(r, norm_id)

    return {
        "device_id": norm_id,
        "agent_online": bool(online),
        "info": info,
    }
