import hashlib
import logging
import secrets
from datetime import datetime, timezone
from typing import Optional, Tuple
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

try:
    import bcrypt
    HAS_BCRYPT = True
except ImportError:
    HAS_BCRYPT = False

from app.models.device import Device, DeviceCredential
from app.schemas.device import DeviceRegisterRequest

logger = logging.getLogger(__name__)


def hash_token(token: str) -> str:
    """Hash a token using SHA-256 for fast constant-time storage & lookup."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def hash_password(password: str) -> str:
    """Hash a PIN/password securely using PBKDF2-HMAC-SHA256 (or bcrypt if available)."""
    salt = secrets.token_hex(16)
    key = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        100_000,
    ).hex()
    return f"pbkdf2_sha256$100000${salt}${key}"


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a plain password against a stored hash."""
    try:
        if hashed.startswith("pbkdf2_sha256$"):
            _, iterations, salt, expected_key = hashed.split("$")
            computed = hashlib.pbkdf2_hmac(
                "sha256",
                plain.encode("utf-8"),
                salt.encode("utf-8"),
                int(iterations),
            ).hex()
            return secrets.compare_digest(computed, expected_key)
        if HAS_BCRYPT:
            return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
        return False
    except Exception:
        return False


async def generate_unique_device_id(db: AsyncSession) -> str:
    """
    Generate a globally unique permanent Device ID:
    Format: AG-XXX-XXX-XXX (e.g. AG-482-193-721)
    """
    for _ in range(50):
        # Generate 9 cryptographically secure random digits
        num = secrets.randbelow(1_000_000_000)
        digits = f"{num:09d}"
        candidate_id = f"AG-{digits[:3]}-{digits[3:6]}-{digits[6:]}"

        result = await db.execute(select(Device.id).where(Device.id == candidate_id))
        if result.scalar_one_or_none() is None:
            return candidate_id

    raise RuntimeError("Failed to allocate a unique Device ID.")


def normalize_device_id(raw_id: str) -> str:
    """
    Normalize user input into AG-XXX-XXX-XXX format.
    Accepts:
      - AG-482-193-721
      - 482193721
      - 482-193-721
      - ag 482 193 721
    """
    cleaned = raw_id.strip().upper().replace(" ", "").replace("_", "")
    if cleaned.startswith("AG-"):
        cleaned = cleaned[3:]
    elif cleaned.startswith("AG"):
        cleaned = cleaned[2:]

    digits = "".join(ch for ch in cleaned if ch.isdigit())
    if len(digits) == 9:
        return f"AG-{digits[:3]}-{digits[3:6]}-{digits[6:]}"

    return raw_id.strip()


async def register_or_recover_device(
    db: AsyncSession,
    request: DeviceRegisterRequest,
    client_ip: Optional[str] = None,
) -> Tuple[Device, str]:
    """
    Registers a new device or authenticates an existing device.
    Returns (Device, raw_auth_token).
    """
    target_id = normalize_device_id(request.device_id) if request.device_id else None
    existing_device: Optional[Device] = None

    if target_id:
        result = await db.execute(
            select(Device).where(Device.id == target_id)
        )
        existing_device = result.scalar_one_or_none()

    now = datetime.now(timezone.utc)

    if existing_device:
        # Load credentials
        cred_res = await db.execute(
            select(DeviceCredential).where(DeviceCredential.device_id == existing_device.id)
        )
        credential = cred_res.scalar_one_or_none()

        # Check authentication token if passed
        raw_token = request.auth_token
        if raw_token and credential and credential.auth_token_hash == hash_token(raw_token):
            # Authenticated existing device! Update metadata
            existing_device.name = request.name
            existing_device.platform = request.platform
            existing_device.agent_version = request.agent_version
            existing_device.status = "online"
            existing_device.last_heartbeat = now
            existing_device.last_ip = client_ip
            existing_device.updated_at = now

            if request.pin and request.unattended_enabled:
                credential.unattended_enabled = True
                credential.pin_hash = hash_password(request.pin)
            elif request.unattended_enabled is False and credential.unattended_enabled:
                credential.unattended_enabled = False

            await db.commit()
            await db.refresh(existing_device)
            return existing_device, raw_token

    # Generate new device ID and token
    new_device_id = await generate_unique_device_id(db)
    raw_auth_token = secrets.token_urlsafe(32)
    hashed_auth_token = hash_token(raw_auth_token)

    new_device = Device(
        id=new_device_id,
        name=request.name or "Remote Device",
        platform=request.platform or "unknown",
        agent_version=request.agent_version or "Remote Support Agent 1.0",
        status="online",
        last_heartbeat=now,
        last_ip=client_ip,
        created_at=now,
        updated_at=now,
    )
    db.add(new_device)
    await db.flush()

    pin_hash = hash_password(request.pin) if request.pin and request.unattended_enabled else None
    credential = DeviceCredential(
        device_id=new_device.id,
        auth_token_hash=hashed_auth_token,
        unattended_enabled=bool(request.unattended_enabled and pin_hash),
        pin_hash=pin_hash,
        updated_at=now,
    )
    db.add(credential)
    await db.commit()
    await db.refresh(new_device)

    logger.info(f"Registered new device: {new_device.id} ({new_device.name})")
    return new_device, raw_auth_token


async def verify_device_token(db: AsyncSession, device_id: str, auth_token: str) -> bool:
    """Verify that an auth token belongs to the given device."""
    normalized = normalize_device_id(device_id)
    cred_res = await db.execute(
        select(DeviceCredential).where(DeviceCredential.device_id == normalized)
    )
    credential = cred_res.scalar_one_or_none()
    if not credential:
        return False
    return secrets.compare_digest(credential.auth_token_hash, hash_token(auth_token))


async def get_device(db: AsyncSession, device_id: str) -> Optional[Device]:
    normalized = normalize_device_id(device_id)
    res = await db.execute(select(Device).where(Device.id == normalized))
    return res.scalar_one_or_none()
