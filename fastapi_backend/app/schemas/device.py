from typing import Optional
from pydantic import BaseModel, Field


class DeviceRegisterRequest(BaseModel):
    device_id: Optional[str] = Field(default=None, max_length=32, description="Existing permanent Device ID if recovered")
    name: str = Field(default="Remote Device", max_length=128)
    platform: str = Field(default="unknown", max_length=64)
    agent_version: str = Field(default="Remote Support Agent 1.0", max_length=32)
    auth_token: Optional[str] = Field(default=None, max_length=128)
    unattended_enabled: Optional[bool] = Field(default=False)
    pin: Optional[str] = Field(default=None, max_length=64)


class DeviceRegisterResponse(BaseModel):
    device_id: str
    auth_token: str
    # Credential for the companion agent (`agent.py --token`); cannot be used to register as host
    agent_token: str
    name: str
    status: str
    agent_version: str
    message: str = "Device registered successfully"


class DeviceTokenRequest(BaseModel):
    auth_token: str = Field("", max_length=128)


class HeartbeatRequest(BaseModel):
    device_id: str = Field(..., max_length=32)
    auth_token: str = Field(..., max_length=128)
    ip: Optional[str] = None
    platform: Optional[str] = None


class HeartbeatResponse(BaseModel):
    status: str
    device_id: str
    server_time: str
    pending_request: Optional[dict] = None


class DeviceResponse(BaseModel):
    id: str
    name: str
    platform: str
    agent_version: str
    status: str
    last_heartbeat: Optional[str] = None
    created_at: Optional[str] = None

    class Config:
        from_attributes = True
