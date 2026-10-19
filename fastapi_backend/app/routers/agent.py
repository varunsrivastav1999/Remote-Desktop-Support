import logging
from typing import Any, Dict
from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse
import httpx

router = APIRouter(prefix="/api/v1/agent", tags=["agent"])
logger = logging.getLogger("remote_support.agent_proxy")

AGENT_HOSTS = ["http://host.docker.internal:8765", "http://127.0.0.1:8765", "http://localhost:8765"]

async def forward_to_agent(method: str, path: str, json_data: Any = None) -> Response:
    """
    Forwards request from HTTPS frontend to local host agent running on host OS,
    preventing browser Mixed Content errors.
    """
    for base_url in AGENT_HOSTS:
        target_url = f"{base_url}/{path.lstrip('/')}"
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                if method == "GET":
                    resp = await client.get(target_url)
                else:
                    resp = await client.post(target_url, json=json_data)
                return Response(
                    content=resp.content,
                    status_code=resp.status_code,
                    media_type=resp.headers.get("content-type", "application/json"),
                )
        except Exception:
            continue

    return JSONResponse(
        status_code=503,
        content={"error": "Native host companion agent not reachable", "status": "offline"},
    )

@router.get("/health")
async def agent_health():
    return await forward_to_agent("GET", "health")

@router.get("/fs/home")
async def agent_fs_home():
    return await forward_to_agent("GET", "fs/home")

@router.post("/{path:path}")
async def agent_proxy_post(path: str, request: Request):
    try:
        data = await request.json()
    except Exception:
        data = {}
    return await forward_to_agent("POST", path, data)

@router.get("/{path:path}")
async def agent_proxy_get(path: str):
    return await forward_to_agent("GET", path)
