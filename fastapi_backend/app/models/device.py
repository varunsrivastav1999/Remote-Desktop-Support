from datetime import datetime, timezone
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import relationship

from app.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Device(Base):
    __tablename__ = "devices"

    id = Column(String(32), primary_key=True, index=True)  # Format: AG-XXX-XXX-XXX
    name = Column(String(128), nullable=False, default="Remote Device")
    platform = Column(String(64), nullable=False, default="unknown")
    agent_version = Column(String(32), nullable=False, default="Remote Support Agent 1.0")
    status = Column(String(32), nullable=False, default="offline", index=True)  # online, offline, in_session
    last_heartbeat = Column(DateTime(timezone=True), nullable=True, default=utcnow)
    last_ip = Column(String(64), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)

    # Relationships
    credential = relationship("DeviceCredential", back_populates="device", uselist=False, cascade="all, delete-orphan")
    outgoing_requests = relationship("ConnectionRequest", foreign_keys="ConnectionRequest.caller_device_id", back_populates="caller")
    incoming_requests = relationship("ConnectionRequest", foreign_keys="ConnectionRequest.target_device_id", back_populates="target")
    hosted_sessions = relationship("DeviceSession", foreign_keys="DeviceSession.host_device_id", back_populates="host")
    joined_sessions = relationship("DeviceSession", foreign_keys="DeviceSession.client_device_id", back_populates="client")


class DeviceCredential(Base):
    __tablename__ = "device_credentials"

    device_id = Column(String(32), ForeignKey("devices.id", ondelete="CASCADE"), primary_key=True)
    auth_token_hash = Column(String(256), nullable=False)
    unattended_enabled = Column(Boolean, nullable=False, default=False)
    pin_hash = Column(String(256), nullable=True)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)

    device = relationship("Device", back_populates="credential")
