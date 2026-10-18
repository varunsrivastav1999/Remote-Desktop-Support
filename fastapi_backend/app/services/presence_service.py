import logging
from datetime import datetime, timezone
from typing import Optional
import redis.asyncio as redis
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.device import Device
from app.services.device_service import normalize_device_id

logger = logging.getLogger(__name__)


def presence_key(device_id: str) -> str:
    return f"device:{device_id}:presence"


def session_peer_key(session_code: str, role: str) -> str:
    return f"session:{session_code}:peer:{role}"


async def set_device_online(redis_client: redis.Redis, device_id: str, ttl: int = 45) -> None:
    norm_id = normalize_device_id(device_id)
    await redis_client.set(presence_key(norm_id), "online", ex=ttl)


async def set_device_offline(redis_client: redis.Redis, device_id: str) -> None:
    norm_id = normalize_device_id(device_id)
    await redis_client.delete(presence_key(norm_id))


async def is_device_online(redis_client: redis.Redis, device_id: str) -> bool:
    norm_id = normalize_device_id(device_id)
    return bool(await redis_client.exists(presence_key(norm_id)))


async def record_heartbeat(
    db: AsyncSession,
    redis_client: redis.Redis,
    device_id: str,
    ip: Optional[str] = None,
    platform: Optional[str] = None,
) -> bool:
    norm_id = normalize_device_id(device_id)
    now = datetime.now(timezone.utc)

    # 1. Update in Redis with TTL
    await set_device_online(redis_client, norm_id, ttl=settings.HEARTBEAT_TIMEOUT_SECONDS)

    # 2. Update in DB
    values = {"last_heartbeat": now, "status": "online"}
    if ip:
        values["last_ip"] = ip
    if platform:
        values["platform"] = platform

    res = await db.execute(
        update(Device).where(Device.id == norm_id).values(**values)
    )
    await db.commit()
    return res.rowcount > 0


async def resolve_device_status(redis_client: redis.Redis, device: Device) -> str:
    """Returns actual real-time status: online, in_session, or offline."""
    online = await is_device_online(redis_client, device.id)
    if not online:
        return "offline"
    if device.status == "in_session":
        return "in_session"
    return "online"
