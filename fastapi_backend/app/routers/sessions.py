import logging
import secrets
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
import redis.asyncio as redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.session import ConnectionRequest, DeviceSession
from app.schemas.session import (
    ConnectionApprovalRequest,
    ConnectionRequestCreate,
    ConnectionRequestResponse,
    LegacySessionCreate,
    LegacySessionJoin,
    LegacySessionRename,
    SessionStatusResponse,
)
from app.services.device_service import normalize_device_id
from app.services.presence_service import is_device_online
from app.services.session_service import (
    create_connection_request,
    issue_request_token,
    process_approval,
    verify_request_token,
)
from app.services.audit_service import log_audit_event

logger = logging.getLogger(__name__)
router = APIRouter(tags=["sessions"])


def get_redis(request: Request) -> redis.Redis:
    return request.app.state.redis


# ═════════════════════════════════════════════════════════════
# Remote Desktop Support V1 Endpoints
# ═════════════════════════════════════════════════════════════

@router.post("/api/v1/sessions/connect", response_model=ConnectionRequestResponse)
async def connect_to_device(
    payload: ConnectionRequestCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Computer A requests connection to Computer B (by Device ID, e.g. AG-735-281-904).
    """
    redis_client = get_redis(request)
    client_ip = request.client.host if request.client else "unknown"

    try:
        conn_req, created_session, message = await create_connection_request(
            db=db,
            redis_client=redis_client,
            caller_device_id=payload.caller_device_id,
            caller_name=payload.caller_name,
            target_device_id=payload.target_device_id,
            pin=payload.pin,
        )

        request_token = await issue_request_token(redis_client, conn_req.id)

        await log_audit_event(
            db,
            event_type="connection_requested",
            device_id=conn_req.target_device_id,
            details={
                "caller": conn_req.caller_device_id,
                "caller_name": conn_req.caller_name,
                "status": conn_req.status,
            },
            ip_address=client_ip,
        )

        return ConnectionRequestResponse(
            request_id=conn_req.id,
            target_device_id=conn_req.target_device_id,
            status=conn_req.status,
            session_token=conn_req.session_token,
            session_code=conn_req.target_device_id if conn_req.status == "accepted" else None,
            ws_url=f"/ws/{conn_req.target_device_id}" if conn_req.status == "accepted" else None,
            message=message,
            request_token=request_token,
        )
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.exception("Failed to create connection request")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/v1/sessions/approve")
async def approve_connection_request(
    payload: ConnectionApprovalRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Computer B accepts or rejects the incoming connection request.
    """
    redis_client = get_redis(request)
    client_ip = request.client.host if request.client else "unknown"

    try:
        conn_req, created_session = await process_approval(
            db=db,
            redis_client=redis_client,
            request_id=payload.request_id,
            accept=payload.accept,
            host_auth_token=payload.auth_token,
        )

        if not conn_req:
            return {
                "status": "ok",
                "request_id": payload.request_id,
                "accepted": payload.accept,
                "session_token": None,
                "session_code": None,
            }

        await log_audit_event(
            db,
            event_type="connection_accepted" if payload.accept else "connection_rejected",
            device_id=conn_req.target_device_id,
            details={"request_id": payload.request_id, "caller": conn_req.caller_device_id},
            ip_address=client_ip,
        )

        return {
            "status": "ok",
            "request_id": conn_req.id,
            "accepted": payload.accept,
            "session_token": conn_req.session_token if payload.accept else None,
            "session_code": conn_req.target_device_id if payload.accept else None,
        }
    except PermissionError as pe:
        raise HTTPException(status_code=403, detail=str(pe))
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.exception("Failed to process approval")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/v1/sessions/request/{request_id}")
async def check_request_status(
    request_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    authorization: Optional[str] = Header(None),
):
    """
    Poll connection request status (useful fallback if WebSocket push dropped).
    Only the caller that created the request may poll it:
    Authorization: Bearer <request_token from /connect>.
    """
    scheme, _, token = (authorization or "").partition(" ")
    token = token.strip() if scheme.lower() == "bearer" else ""
    if not await verify_request_token(get_redis(request), request_id, token):
        raise HTTPException(status_code=401, detail="Invalid request token")

    res = await db.execute(select(ConnectionRequest).where(ConnectionRequest.id == request_id))
    conn_req = res.scalar_one_or_none()
    if not conn_req:
        raise HTTPException(status_code=404, detail="Request not found")

    return {
        "request_id": conn_req.id,
        "target_device_id": conn_req.target_device_id,
        "status": conn_req.status,
        "session_token": conn_req.session_token,
        "session_code": conn_req.target_device_id if conn_req.status == "accepted" else None,
        "ws_url": f"/ws/{conn_req.target_device_id}" if conn_req.status == "accepted" else None,
    }


# ═════════════════════════════════════════════════════════════
# Legacy API Compatibility Layer
# ═════════════════════════════════════════════════════════════

@router.post("/api/session/create/", status_code=status.HTTP_201_CREATED)
async def legacy_create_session(
    payload: LegacySessionCreate,
    request: Request,
):
    """Legacy endpoint: creates or recovers a desk session code."""
    redis_client = get_redis(request)
    code = ""
    host_token = secrets.token_urlsafe(32)

    if payload.device_id:
        norm_id = normalize_device_id(payload.device_id)
        # Check if mapped to a code
        mapped_code = await redis_client.get(f"device:{norm_id}:session")
        if mapped_code:
            code = mapped_code

    if not code:
        # Generate clean 9-digit code
        for _ in range(25):
            num = secrets.randbelow(1_000_000_000)
            digits = f"{num:09d}"
            cand = f"{digits[:3]}-{digits[3:6]}-{digits[6:]}"
            if not await redis_client.exists(f"session:{cand}"):
                code = cand
                break

    now_iso = datetime.now(timezone.utc).isoformat()
    await redis_client.hset(
        f"session:{code}",
        mapping={
            "host_token": host_token,
            "host_identifier": payload.host_identifier,
            "alias": payload.alias,
            "created_at": now_iso,
        },
    )
    await redis_client.expire(f"session:{code}", 2592000)

    if payload.device_id:
        norm_id = normalize_device_id(payload.device_id)
        await redis_client.set(f"device:{norm_id}:session", code, ex=2592000)

    return {
        "code": code,
        "host_token": host_token,
        "alias": payload.alias,
        "host_identifier": payload.host_identifier,
        "status": "registering",
        "host_online": False,
        "created_at": now_iso,
    }


@router.post("/api/session/join/")
async def legacy_join_session(
    payload: LegacySessionJoin,
    request: Request,
):
    redis_client = get_redis(request)
    raw = payload.code.strip()
    digits = "".join(c for c in raw if c.isdigit())
    code = f"{digits[:3]}-{digits[3:6]}-{digits[6:]}" if len(digits) == 9 else raw

    session = await redis_client.hgetall(f"session:{code}")
    if not session:
        # Try device ID lookup
        norm_device = normalize_device_id(raw)
        mapped = await redis_client.get(f"device:{norm_device}:session")
        if mapped:
            code = mapped
            session = await redis_client.hgetall(f"session:{code}")

    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")

    host_online = bool(await redis_client.exists(f"session:{code}:peer:host"))
    if not host_online:
        raise HTTPException(status_code=409, detail="The remote desk is not online.")

    return {
        "session": {
            "id": code,
            "code": code,
            "alias": session.get("alias", ""),
            "host_identifier": session.get("host_identifier", ""),
            "status": "connected",
            "host_online": True,
            "created_at": session.get("created_at", ""),
        },
        "ws_url": f"/ws/{code}",
    }


@router.get("/api/session/{code}/")
async def legacy_get_session(
    code: str,
    request: Request,
):
    redis_client = get_redis(request)
    raw = code.strip()
    digits = "".join(c for c in raw if c.isdigit())
    clean_code = f"{digits[:3]}-{digits[3:6]}-{digits[6:]}" if len(digits) == 9 else raw

    session = await redis_client.hgetall(f"session:{clean_code}")
    if not session:
        norm = normalize_device_id(clean_code)
        session = await redis_client.hgetall(f"session:{norm}")
        if session:
            clean_code = norm

    if not session:
        from app.database import async_session_factory
        from app.services.device_service import get_device
        from app.services.presence_service import is_device_online
        try:
            async with async_session_factory() as db:
                dev = await get_device(db, clean_code)
                if dev:
                    online = await is_device_online(redis_client, dev.id)
                    return {
                        "id": dev.id,
                        "code": dev.id,
                        "alias": dev.name,
                        "host_identifier": dev.name,
                        "status": "connected" if online else "offline",
                        "host_online": online,
                        "created_at": str(dev.created_at),
                    }
        except Exception as e:
            logger.debug(f"Device fallback check failed for {clean_code}: {e}")

        raise HTTPException(status_code=404, detail="Session not found.")

    host_online = bool(await redis_client.exists(f"session:{clean_code}:peer:host"))
    return {
        "id": clean_code,
        "code": clean_code,
        "alias": session.get("alias", ""),
        "host_identifier": session.get("host_identifier", ""),
        "status": "connected" if host_online else "offline",
        "host_online": host_online,
        "created_at": session.get("created_at", ""),
    }


@router.patch("/api/session/{code}/rename/")
async def legacy_rename_session(
    code: str,
    payload: LegacySessionRename,
    request: Request,
    x_host_token: Optional[str] = Header(default=None),
):
    redis_client = get_redis(request)
    clean_code = code.strip()
    session = await redis_client.hgetall(f"session:{clean_code}")
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")

    if not x_host_token or not secrets.compare_digest(session.get("host_token", ""), x_host_token):
        raise HTTPException(status_code=403, detail="Only the hosting desk can rename this session.")

    await redis_client.hset(f"session:{clean_code}", "alias", payload.alias)
    return {"status": "ok", "alias": payload.alias}
