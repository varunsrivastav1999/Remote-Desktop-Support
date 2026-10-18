from datetime import datetime, timezone
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ConnectionRequest(Base):
    __tablename__ = "connection_requests"

    id = Column(String(64), primary_key=True, index=True)
    caller_device_id = Column(String(32), ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, index=True)
    caller_name = Column(String(128), nullable=False, default="Remote Caller")
    target_device_id = Column(String(32), ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(String(32), nullable=False, default="pending", index=True)  # pending, accepted, rejected, expired, canceled
    session_token = Column(String(128), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    expires_at = Column(DateTime(timezone=True), nullable=False)

    caller = relationship("Device", foreign_keys=[caller_device_id], back_populates="outgoing_requests")
    target = relationship("Device", foreign_keys=[target_device_id], back_populates="incoming_requests")


class DeviceSession(Base):
    __tablename__ = "device_sessions"

    id = Column(String(64), primary_key=True, index=True)  # Unique session UUID
    session_code = Column(String(32), nullable=False, index=True)  # Device ID or 9-digit code
    host_device_id = Column(String(32), ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, index=True)
    client_device_id = Column(String(32), ForeignKey("devices.id", ondelete="SET NULL"), nullable=True, index=True)
    session_token = Column(String(128), nullable=False)
    status = Column(String(32), nullable=False, default="waiting", index=True)  # waiting, negotiating, connected, ended, failed
    connection_type = Column(String(32), nullable=False, default="unknown")  # direct_lan, stun_p2p, turn_relay, unknown
    started_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    connected_at = Column(DateTime(timezone=True), nullable=True)
    ended_at = Column(DateTime(timezone=True), nullable=True)
    duration_seconds = Column(Integer, nullable=False, default=0)

    host = relationship("Device", foreign_keys=[host_device_id], back_populates="hosted_sessions")
    client = relationship("Device", foreign_keys=[client_device_id], back_populates="joined_sessions")
