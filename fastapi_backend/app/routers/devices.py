import logging
from typing import List
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
import redis.asyncio as redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.device import Device
from app.schemas.device import (
    DeviceRegisterRequest,
    DeviceRegisterResponse,
    DeviceResponse,
    HeartbeatRequest,
    HeartbeatResponse,
)
from app.services.device_service import (
    get_device,
    normalize_device_id,
    register_or_recover_device,
    verify_device_token,
)
from app.services.presence_service import (
    record_heartbeat,
    resolve_device_status,
)
from app.services.audit_service import log_audit_event

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/devices", tags=["devices"])


def get_redis(request: Request) -> redis.Redis:
    return request.app.state.redis


@router.post("/register", response_model=DeviceRegisterResponse, status_code=status.HTTP_201_CREATED)
async def register_device(
    payload: DeviceRegisterRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Registers a new device or recovers an existing permanent Device ID.
    """
    client_ip = request.client.host if request.client else "unknown"
    try:
        device, auth_token = await register_or_recover_device(db, payload, client_ip=client_ip)
        redis_client = get_redis(request)
        await record_heartbeat(db, redis_client, device.id, ip=client_ip, platform=device.platform)

        # Initialize session room for this device ID so WebRTC signaling connects immediately
        await redis_client.hset(
            f"session:{device.id}",
            mapping={
                "status": "waiting",
                "device_id": device.id,
                "host_token": auth_token,
                "created_at": str(device.created_at),
            },
        )
        await redis_client.expire(f"session:{device.id}", 86400)

        await log_audit_event(
            db,
            event_type="device_registered",
            device_id=device.id,
            details={"name": device.name, "platform": device.platform, "version": device.agent_version},
            ip_address=client_ip,
        )

        return DeviceRegisterResponse(
            device_id=device.id,
            auth_token=auth_token,
            name=device.name,
            status="online",
            agent_version=device.agent_version,
            message="Device registered and online",
        )
    except Exception as e:
        logger.exception("Failed to register device")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/heartbeat", response_model=HeartbeatResponse)
async def device_heartbeat(
    payload: HeartbeatRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Periodic heartbeat from host agent (every 15-30s).
    """
    client_ip = request.client.host if request.client else "unknown"
    norm_id = normalize_device_id(payload.device_id)

    # Verify device token
    is_valid = await verify_device_token(db, norm_id, payload.auth_token)
    if not is_valid:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid device credentials")

    redis_client = get_redis(request)
    await record_heartbeat(db, redis_client, norm_id, ip=payload.ip or client_ip, platform=payload.platform)

    # Ensure session room key has host_token and is refreshed
    await redis_client.hset(
        f"session:{norm_id}",
        mapping={
            "status": "waiting",
            "device_id": norm_id,
            "host_token": payload.auth_token,
        },
    )
    await redis_client.expire(f"session:{norm_id}", 86400)

    import json
    pending_payload = None
    pending_raw = await redis_client.get(f"device:{norm_id}:pending_request")
    if pending_raw:
        try:
            pending_payload = json.loads(pending_raw)
        except Exception:
            pass

    from datetime import datetime, timezone
    return HeartbeatResponse(
        status="ok",
        device_id=norm_id,
        server_time=datetime.now(timezone.utc).isoformat(),
        pending_request=pending_payload,
    )


@router.get("/{device_id}", response_model=DeviceResponse)
async def get_device_info(
    device_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Lookup a device by Device ID to check if it exists and is online.
    """
    device = await get_device(db, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    redis_client = get_redis(request)
    current_status = await resolve_device_status(redis_client, device)

    return DeviceResponse(
        id=device.id,
        name=device.name,
        platform=device.platform,
        agent_version=device.agent_version,
        status=current_status,
        last_heartbeat=device.last_heartbeat.isoformat() if device.last_heartbeat else None,
        created_at=device.created_at.isoformat() if device.created_at else None,
    )


@router.get("", response_model=List[DeviceResponse])
async def list_devices(
    request: Request,
    db: AsyncSession = Depends(get_db),
    limit: int = 50,
):
    """
    List known devices with real-time presence.
    """
    res = await db.execute(select(Device).order_by(Device.updated_at.desc()).limit(limit))
    devices = res.scalars().all()

    redis_client = get_redis(request)
    output = []
    for d in devices:
        st = await resolve_device_status(redis_client, d)
        output.append(
            DeviceResponse(
                id=d.id,
                name=d.name,
                platform=d.platform,
                agent_version=d.agent_version,
                status=st,
                last_heartbeat=d.last_heartbeat.isoformat() if d.last_heartbeat else None,
                created_at=d.created_at.isoformat() if d.created_at else None,
            )
        )
    return output
