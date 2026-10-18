import logging
from fastapi import APIRouter, Request
from sqlalchemy import text
from app.database import engine

logger = logging.getLogger(__name__)
router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check(request: Request):
    redis_ok = False
    db_ok = False

    # Check Redis
    try:
        redis_client = request.app.state.redis
        await redis_client.ping()
        redis_ok = True
    except Exception as e:
        logger.warning(f"Redis healthcheck failed: {e}")

    # Check Database
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        db_ok = True
    except Exception as e:
        logger.warning(f"Database healthcheck failed: {e}")

    status_str = "ok" if (redis_ok and db_ok) else "degraded"
    return {
        "status": status_str,
        "service": "Remote Desktop Support Server",
        "redis": "connected" if redis_ok else "unavailable",
        "database": "connected" if db_ok else "unavailable",
    }
