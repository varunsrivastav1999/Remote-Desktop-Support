import json
import logging
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple
import redis.asyncio as redis
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.device import Device, DeviceCredential
from app.models.session import ConnectionRequest, DeviceSession
from app.services.device_service import normalize_device_id, verify_password
from app.services.presence_service import is_device_online

logger = logging.getLogger(__name__)


def device_channel(device_id: str) -> str:
    return f"channel:device:{device_id}"


def session_channel(session_code: str) -> str:
    return f"channel:session:{session_code}"


async def create_connection_request(
    db: AsyncSession,
    redis_client: redis.Redis,
    caller_device_id: str,
    caller_name: str,
    target_device_id: str,
    pin: Optional[str] = None,
) -> Tuple[ConnectionRequest, Optional[DeviceSession], str]:
    """
    Creates a connection request from Computer A to Computer B.
    If unattended access is configured on target with matching PIN, auto-approves.
    Returns (ConnectionRequest, DeviceSession or None, message).
    """
    caller_id = normalize_device_id(caller_device_id)
    target_id = normalize_device_id(target_device_id)

    if caller_id == target_id:
        raise ValueError("Cannot connect to your own device.")

    # Validate target exists
    target_res = await db.execute(select(Device).where(Device.id == target_id))
    target = target_res.scalar_one_or_none()
    if not target:
        raise ValueError(f"Target device {target_id} not found.")

    # Validate target online
    online = await is_device_online(redis_client, target_id)
    if not online:
        raise ValueError(f"Device {target_id} is currently offline.")

    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(seconds=settings.CONNECTION_REQUEST_TTL_SECONDS)
    request_id = str(uuid.uuid4())

    # Check unattended access
    cred_res = await db.execute(select(DeviceCredential).where(DeviceCredential.device_id == target_id))
    credential = cred_res.scalar_one_or_none()

    auto_accept = False
    if credential and credential.unattended_enabled and credential.pin_hash and pin:
        if verify_password(pin, credential.pin_hash):
            auto_accept = True
            logger.info(f"Unattended access authorized for {caller_id} -> {target_id}")

    session_token = secrets.token_urlsafe(32) if auto_accept else None
    status = "accepted" if auto_accept else "pending"

    conn_request = ConnectionRequest(
        id=request_id,
        caller_device_id=caller_id,
        caller_name=caller_name or "Remote Client",
        target_device_id=target_id,
        status=status,
        session_token=session_token,
        created_at=now,
        expires_at=expires_at,
    )
    db.add(conn_request)

    created_session: Optional[DeviceSession] = None
    if auto_accept:
        session_id = str(uuid.uuid4())
        created_session = DeviceSession(
            id=session_id,
            session_code=target_id,
            host_device_id=target_id,
            client_device_id=caller_id,
            session_token=session_token,
            status="negotiating",
            connection_type="unknown",
            started_at=now,
        )
        db.add(created_session)
        # Store in Redis for fast signaling auth
        await redis_client.hset(
            f"session:{target_id}",
            mapping={
                "session_id": session_id,
                "session_token": session_token,
                "host_device_id": target_id,
                "client_device_id": caller_id,
                "created_at": now.isoformat(),
            },
        )
        await redis_client.expire(f"session:{target_id}", settings.SESSION_TTL_SECONDS)

    await db.commit()
    await db.refresh(conn_request)

    # Publish notification to target device
    await redis_client.publish(
        device_channel(target_id),
        json.dumps({
            "type": "connection_request" if not auto_accept else "unattended_session_started",
            "request_id": request_id,
            "caller_device_id": caller_id,
            "caller_name": caller_name,
            "session_token": session_token,
            "session_code": target_id,
            "auto_accept": auto_accept,
        }),
    )

    msg = "Connected via unattended access" if auto_accept else "Waiting for remote host approval..."
    return conn_request, created_session, msg


async def process_approval(
    db: AsyncSession,
    redis_client: redis.Redis,
    request_id: str,
    accept: bool,
    host_auth_token: str,
) -> Tuple[ConnectionRequest, Optional[DeviceSession]]:
    """
    Processes host user's Accept / Reject response to incoming connection request.
    """
    req_res = await db.execute(select(ConnectionRequest).where(ConnectionRequest.id == request_id))
    conn_req = req_res.scalar_one_or_none()
    if not conn_req:
        raise ValueError("Connection request not found.")

    if conn_req.status != "pending":
        raise ValueError(f"Request is already {conn_req.status}.")

    now = datetime.now(timezone.utc)
    expires_at = conn_req.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    if expires_at < now:
        conn_req.status = "expired"
        await db.commit()
        raise ValueError("Connection request has expired.")

    # Verify that the approver is the actual target device
    cred_res = await db.execute(select(DeviceCredential).where(DeviceCredential.device_id == conn_req.target_device_id))
    credential = cred_res.scalar_one_or_none()
    import hashlib
    hashed = hashlib.sha256(host_auth_token.encode("utf-8")).hexdigest()
    if not credential or not secrets.compare_digest(credential.auth_token_hash, hashed):
        raise PermissionError("Unauthorized device attempting approval.")

    created_session = None
    if accept:
        session_token = secrets.token_urlsafe(32)
        conn_req.status = "accepted"
        conn_req.session_token = session_token

        session_id = str(uuid.uuid4())
        created_session = DeviceSession(
            id=session_id,
            session_code=conn_req.target_device_id,
            host_device_id=conn_req.target_device_id,
            client_device_id=conn_req.caller_device_id,
            session_token=session_token,
            status="negotiating",
            connection_type="unknown",
            started_at=now,
        )
        db.add(created_session)

        # Store in Redis for signaling lookup
        await redis_client.hset(
            f"session:{conn_req.target_device_id}",
            mapping={
                "session_id": session_id,
                "session_token": session_token,
                "host_device_id": conn_req.target_device_id,
                "client_device_id": conn_req.caller_device_id,
                "created_at": now.isoformat(),
            },
        )
        await redis_client.expire(f"session:{conn_req.target_device_id}", settings.SESSION_TTL_SECONDS)

        # Notify caller via Redis channel
        await redis_client.publish(
            device_channel(conn_req.caller_device_id),
            json.dumps({
                "type": "connection_accepted",
                "request_id": request_id,
                "target_device_id": conn_req.target_device_id,
                "session_token": session_token,
                "session_code": conn_req.target_device_id,
                "ws_url": f"/ws/{conn_req.target_device_id}",
            }),
        )
    else:
        conn_req.status = "rejected"
        await redis_client.publish(
            device_channel(conn_req.caller_device_id),
            json.dumps({
                "type": "connection_rejected",
                "request_id": request_id,
                "target_device_id": conn_req.target_device_id,
                "message": "Connection request rejected by remote host.",
            }),
        )

    await db.commit()
    await db.refresh(conn_req)
    return conn_req, created_session
