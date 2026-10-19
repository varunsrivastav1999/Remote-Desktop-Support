import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import redis.asyncio as redis

from app.config import settings
from app.database import init_db
from app.routers import (
    devices_router,
    health_router,
    sessions_router,
    signaling_router,
    terminal_router,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("remote_support")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting Remote Desktop Support Server...")
    try:
        await init_db()
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")

    try:
        app.state.redis = redis.from_url(settings.REDIS_URL, decode_responses=True)
        await app.state.redis.ping()
        logger.info(f"Connected to Redis at {settings.REDIS_URL}")
    except Exception as e:
        logger.error(f"Could not connect to Redis: {e}")

    yield

    # Shutdown
    logger.info("Shutting down Remote Desktop Support Server...")
    if hasattr(app.state, "redis") and app.state.redis:
        await app.state.redis.aclose()


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=settings.cors_origins != ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(health_router)
app.include_router(devices_router)
app.include_router(sessions_router)
app.include_router(signaling_router)
app.include_router(terminal_router)
