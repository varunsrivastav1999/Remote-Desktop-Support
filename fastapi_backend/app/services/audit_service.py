import json
import logging
from typing import Any, Dict, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog

logger = logging.getLogger(__name__)


async def log_audit_event(
    db: AsyncSession,
    event_type: str,
    device_id: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    ip_address: Optional[str] = None,
) -> None:
    try:
        entry = AuditLog(
            device_id=device_id,
            event_type=event_type,
            details=json.dumps(details) if details else None,
            ip_address=ip_address,
        )
        db.add(entry)
        await db.commit()
    except Exception as e:
        logger.error(f"Failed to record audit log: {e}")
