import asyncio
import os
import sys

# Ensure backend root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.database import Base, engine, async_session_factory
from app.models.device import Device, DeviceCredential
from app.models.session import ConnectionRequest, DeviceSession
from app.services.device_service import (
    generate_unique_device_id,
    normalize_device_id,
    register_or_recover_device,
    verify_device_token,
)
from app.services.presence_service import is_device_online, record_heartbeat
from app.services.session_service import create_connection_request, process_approval
from app.schemas.device import DeviceRegisterRequest


class MockRedis:
    def __init__(self):
        self.store = {}
        self.hashes = {}
        self.pubsub_channels = {}

    async def ping(self):
        return True

    async def set(self, key, val, ex=None, nx=False):
        if nx and key in self.store:
            return False
        self.store[key] = val
        return True

    async def get(self, key):
        return self.store.get(key)

    async def exists(self, key):
        return 1 if key in self.store or key in self.hashes else 0

    async def delete(self, key):
        removed = (1 if key in self.store else 0) + (1 if key in self.hashes else 0)
        self.store.pop(key, None)
        self.hashes.pop(key, None)
        return removed

    async def expire(self, key, seconds):
        return 1

    async def hset(self, name, key=None, value=None, mapping=None):
        if name not in self.hashes:
            self.hashes[name] = {}
        if mapping:
            self.hashes[name].update(mapping)
        elif key:
            self.hashes[name][key] = value
        return True

    async def hgetall(self, name):
        return self.hashes.get(name, {})

    async def publish(self, channel, message):
        return 1

    async def aclose(self):
        pass


async def run_tests():
    print("--- [TEST 1] Testing Database Schema Creation ---")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("Database tables created successfully!")

    mock_redis = MockRedis()

    print("\n--- [TEST 2] Testing Device ID Format and Normalization ---")
    assert normalize_device_id("ag-123-456-789") == "AG-123-456-789"
    assert normalize_device_id("123456789") == "AG-123-456-789"
    assert normalize_device_id("AG 482 193 721") == "AG-482-193-721"
    print("Device ID normalization passed!")

    print("\n--- [TEST 3] Testing Device Registration (Laptop A & Laptop B) ---")
    async with async_session_factory() as db:
        # Register Laptop A
        req_a = DeviceRegisterRequest(
            name="Laptop A (MacBook)",
            platform="macos",
            agent_version="Remote Support Agent 1.0",
        )
        dev_a, token_a = await register_or_recover_device(db, req_a, client_ip="192.168.1.101")
        assert dev_a.id.startswith("AG-"), f"Invalid ID format: {dev_a.id}"
        assert len(dev_a.id) == 14, f"Expected 14 chars AG-XXX-XXX-XXX, got {len(dev_a.id)}"
        assert await verify_device_token(db, dev_a.id, token_a) is True
        print(f"Registered Laptop A -> Device ID: {dev_a.id}, Token: {token_a[:8]}...")

        # Register Laptop B with unattended PIN
        req_b = DeviceRegisterRequest(
            name="Laptop B (Ubuntu)",
            platform="linux",
            agent_version="Remote Support Agent 1.0",
            unattended_enabled=True,
            pin="securePIN123",
        )
        dev_b, token_b = await register_or_recover_device(db, req_b, client_ip="192.168.1.102")
        assert dev_b.id.startswith("AG-")
        assert dev_a.id != dev_b.id, "Device IDs must be unique!"
        print(f"Registered Laptop B -> Device ID: {dev_b.id}")

    print("\n--- [TEST 4] Testing Heartbeat and Presence ---")
    async with async_session_factory() as db:
        await record_heartbeat(db, mock_redis, dev_a.id, ip="192.168.1.101")
        await record_heartbeat(db, mock_redis, dev_b.id, ip="192.168.1.102")
        assert await is_device_online(mock_redis, dev_a.id) is True
        assert await is_device_online(mock_redis, dev_b.id) is True
        print("Presence recorded in Redis and DB successfully!")

    print("\n--- [TEST 5] Testing Connection Request: Laptop A -> Laptop B ---")
    async with async_session_factory() as db:
        # Test connection request requiring approval
        conn_req, session, msg = await create_connection_request(
            db=db,
            redis_client=mock_redis,
            caller_device_id=dev_a.id,
            caller_name="Laptop A",
            target_device_id=dev_b.id,
            pin=None,  # No PIN provided -> manual approval required
        )
        assert conn_req.status == "pending"
        print(f"Connection request created: ID={conn_req.id}, Status={conn_req.status}")

        # Laptop B approves
        approved_req, approved_session = await process_approval(
            db=db,
            redis_client=mock_redis,
            request_id=conn_req.id,
            accept=True,
            host_auth_token=token_b,
        )
        assert approved_req.status == "accepted"
        assert approved_session is not None
        assert approved_session.session_token is not None
        session_hash = mock_redis.hashes.get(f"session:{dev_b.id}")
        assert session_hash is not None and session_hash.get("host_token") == token_b
        print(f"Request accepted! Session token: {approved_session.session_token[:8]}..., Host token verified in Redis")

    print("\n--- [TEST 6] Testing Unattended Access with PIN ---")
    async with async_session_factory() as db:
        conn_req2, session2, msg2 = await create_connection_request(
            db=db,
            redis_client=mock_redis,
            caller_device_id=dev_a.id,
            caller_name="Laptop A",
            target_device_id=dev_b.id,
            pin="securePIN123",  # Correct PIN -> Auto-accept!
        )
        assert conn_req2.status == "accepted"
        assert session2 is not None
        print(f"Unattended connection auto-accepted! Token: {session2.session_token[:8]}...")

    print("\n--- [TEST 7] Testing FastAPI HTTP Endpoints via AsyncClient ---")
    import httpx
    from app.main import app

    app.state.redis = mock_redis
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # Health check
        res_health = await client.get("/health")
        assert res_health.status_code == 200
        assert res_health.json()["service"] == "Remote Desktop Support Server"
        print("Health check endpoint passed!")

        # Register endpoint
        res_reg = await client.post("/api/v1/devices/register", json={
            "name": "Test Client Laptop",
            "platform": "windows",
            "agent_version": "Remote Support Agent 1.0",
        })
        assert res_reg.status_code == 201
        reg_data = res_reg.json()
        assert reg_data["device_id"].startswith("AG-")
        client_device_id = reg_data["device_id"]
        client_auth_token = reg_data["auth_token"]
        print(f"HTTP Device Register passed: {client_device_id}")

        # Heartbeat endpoint
        res_hb = await client.post("/api/v1/devices/heartbeat", json={
            "device_id": client_device_id,
            "auth_token": client_auth_token,
        })
        assert res_hb.status_code == 200
        print("HTTP Heartbeat endpoint passed!")

        # Device lookup endpoint
        res_lookup = await client.get(f"/api/v1/devices/{client_device_id}")
        assert res_lookup.status_code == 200
        assert res_lookup.json()["id"] == client_device_id
        print("HTTP Device Lookup passed!")

        # Legacy session create
        res_legacy = await client.post("/api/session/create/", json={
            "host_identifier": "Desk 1",
            "alias": "desk-one",
        })
        assert res_legacy.status_code == 201
        legacy_code = res_legacy.json()["code"]
        print(f"Legacy create session passed: {legacy_code}")

    print("\n==========================================")
    print(">>> ALL BACKEND & DATABASE TESTS PASSED! <<<")
    print("==========================================")


if __name__ == "__main__":
    asyncio.run(run_tests())
