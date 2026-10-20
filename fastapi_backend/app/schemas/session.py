from typing import Optional
from pydantic import BaseModel, Field


class ConnectionRequestCreate(BaseModel):
    caller_device_id: str = Field(..., max_length=32)
    caller_name: str = Field(default="Remote Client", max_length=128)
    target_device_id: str = Field(..., max_length=32)
    pin: Optional[str] = Field(default=None, max_length=64)


class ConnectionRequestResponse(BaseModel):
    request_id: str
    target_device_id: str
    status: str  # pending, accepted, rejected, offline
    session_token: Optional[str] = None
    session_code: Optional[str] = None
    ws_url: Optional[str] = None
    message: str
    # Secret for polling GET /api/v1/sessions/request/{request_id}; only this caller gets it
    request_token: Optional[str] = None


class ConnectionApprovalRequest(BaseModel):
    request_id: str = Field(..., max_length=64)
    accept: bool
    auth_token: str = Field(..., max_length=128)


class SessionStatusResponse(BaseModel):
    id: str
    session_code: str
    host_device_id: str
    client_device_id: Optional[str] = None
    status: str
    connection_type: str
    started_at: str
    duration_seconds: int = 0

    class Config:
        from_attributes = True


# Backward compatibility schemas for legacy endpoints
class LegacySessionCreate(BaseModel):
    host_identifier: str = Field(default="", max_length=255)
    alias: str = Field(default="", max_length=100)
    device_id: str = Field(default="", max_length=128)


class LegacySessionJoin(BaseModel):
    code: str = Field(min_length=3, max_length=100)


class LegacySessionRename(BaseModel):
    alias: str = Field(default="", max_length=100)
