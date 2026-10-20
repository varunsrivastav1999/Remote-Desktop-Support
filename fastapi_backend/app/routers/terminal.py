import asyncio
import json
import logging
import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.services.device_service import normalize_device_id, verify_device_token

router = APIRouter(prefix="/api/v1/terminal", tags=["terminal"])
logger = logging.getLogger("remote_support.terminal")

class TerminalExecRequest(BaseModel):
    command: str
    device_id: Optional[str] = None
    # The target device's own token: only that device may run commands on itself this way
    auth_token: Optional[str] = None
    cwd: Optional[str] = None

@router.post("/exec")
async def execute_terminal_command(
    payload: TerminalExecRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Executes a shell command on the target remote system via its companion agent.
    Never executes on the local server.
    """
    cmd = payload.command.strip()
    if not cmd:
        return {"stdout": "", "stderr": "", "exit_code": 0}

    device_id = payload.device_id
    if not device_id:
        return {
            "stdout": "",
            "stderr": "Error: Target device_id must be specified. Terminal execution operates strictly on remote connected systems, never on the central server.\n",
            "exit_code": 1,
        }

    norm_id = normalize_device_id(device_id)
    if not payload.auth_token or not await verify_device_token(db, norm_id, payload.auth_token):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid device credentials")
    redis_client = request.app.state.redis

    # Check if agent is online for this device
    agent_online = await redis_client.exists(f"device:{norm_id}:agent_online")
    if not agent_online:
        return {
            "stdout": "",
            "stderr": f"Error: Remote companion agent for {norm_id} is offline. Start the companion agent on the remote machine to execute commands.\n",
            "exit_code": 1,
        }

    # Dispatch to remote agent via Redis PubSub
    req_id = f"term_{uuid.uuid4().hex[:8]}"
    agent_channel = f"channel:agent:{norm_id}"
    session_channel = f"channel:session:{norm_id}"

    pubsub = redis_client.pubsub()
    await pubsub.subscribe(session_channel)

    try:
        await redis_client.publish(agent_channel, json.dumps({
            "type": "terminal",
            "req_id": req_id,
            "command": cmd,
            "cwd": payload.cwd or None,
        }))

        loop = asyncio.get_running_loop()
        deadline = loop.time() + 15.0

        while loop.time() < deadline:
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if message and message["type"] == "message":
                try:
                    event = json.loads(message["data"])
                    data = event.get("data", event)
                    if data.get("req_id") == req_id:
                        return {
                            "stdout": data.get("stdout", ""),
                            "stderr": data.get("stderr", ""),
                            "exit_code": data.get("exit_code", 0),
                            "cwd": data.get("cwd"),
                        }
                except Exception:
                    pass
            await asyncio.sleep(0.05)

        return {"stdout": "", "stderr": "Command timed out waiting for remote device response (15s limit)\n", "exit_code": 124}
    except Exception as e:
        return {"stdout": "", "stderr": f"Remote execution error: {e}\n", "exit_code": 1}
    finally:
        await pubsub.unsubscribe(session_channel)
        await pubsub.aclose()
