from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class SignalingMessage(BaseModel):
    type: str = Field(..., description="Message type: offer, answer, ice, ping, register, etc.")
    role: Optional[str] = None
    sdp: Optional[Dict[str, Any]] = None
    candidate: Optional[Dict[str, Any]] = None
    host_token: Optional[str] = None
    session_token: Optional[str] = None
    message: Optional[str] = None
