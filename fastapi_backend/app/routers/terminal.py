import logging
import subprocess
from typing import Optional
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1/terminal", tags=["terminal"])
logger = logging.getLogger("remote_support.terminal")

class TerminalExecRequest(BaseModel):
    command: str
    cwd: Optional[str] = None

@router.post("/exec")
async def execute_terminal_command(payload: TerminalExecRequest):
    """
    Executes a shell command in the backend environment and returns standard output and error.
    """
    cmd = payload.command.strip()
    if not cmd:
        return {"stdout": "", "stderr": "", "exit_code": 0}
    try:
        proc = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=15,
            cwd=payload.cwd or None,
        )
        return {
            "stdout": proc.stdout,
            "stderr": proc.stderr,
            "exit_code": proc.returncode,
        }
    except subprocess.TimeoutExpired:
        return {"stdout": "", "stderr": "Command timed out (15s limit)\n", "exit_code": 124}
    except Exception as e:
        return {"stdout": "", "stderr": f"Execution error: {e}\n", "exit_code": 1}
