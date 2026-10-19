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
    agent_router,
    ssh_router,
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

import os
from fastapi import Response

# Register routers
app.include_router(health_router)
app.include_router(devices_router)
app.include_router(sessions_router)
app.include_router(signaling_router)
app.include_router(terminal_router)
app.include_router(agent_router)
app.include_router(ssh_router)


@app.get("/agent.py")
async def get_companion_agent():
    candidates = [
        os.path.join(os.path.dirname(__file__), "agent_script.py"),
        "/app/app/agent_script.py",
        "/app/agent_script.py",
        "/workspace/scripts/local_agent.py",
        os.path.join(os.path.dirname(__file__), "..", "..", "scripts", "local_agent.py"),
    ]
    for p in candidates:
        if os.path.exists(p):
            with open(p, "r", encoding="utf-8") as f:
                return Response(content=f.read(), media_type="text/x-python")
    return Response(content="# Companion agent script not found", status_code=404)

