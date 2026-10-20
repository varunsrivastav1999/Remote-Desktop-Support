"""Regression tests for the companion-agent attack surface.

Each test covers one hole that let someone who only knew a Device ID reach the agent:
  1. the unauthenticated REST dispatch (/api/v1/agent/{id}/{action}, /api/v1/terminal/exec)
  2. host registration on /ws/{id} without a valid token
  3. the agent's local HTTP server on 127.0.0.1:8765 (CORS *)
  4. agent impersonation on /ws/agent/{id}
plus re-registering an existing Device ID with a new token, which would defeat every token check.

Run against an isolated stack, never the live one:
    BASE_URL=http://127.0.0.1:18000 python tests/test_agent_security.py
"""
import asyncio
import importlib.util
import json
import os
import secrets
import socket
import sys
import types
import urllib.error
import urllib.request

import websockets

BASE_URL = os.environ.get("BASE_URL", "http://127.0.0.1:8000")
WS_BASE = BASE_URL.replace("http://", "ws://").replace("https://", "wss://")

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
AGENT_COPIES = [
    os.path.join(TESTS_DIR, "..", "app", "agent_script.py"),
    os.path.join(TESTS_DIR, "..", "..", "scripts", "local_agent.py"),
    os.path.join(TESTS_DIR, "..", "..", "tauri_agent", "public", "agent.py"),
]


def http(method, path, body=None):
    """Return (status, parsed JSON or text) without raising on HTTP errors."""
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        f"{BASE_URL}{path}", data=data, method=method,
        headers={"Content-Type": "application/json"} if data else {},
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            status, raw = resp.status, resp.read().decode()
    except urllib.error.HTTPError as err:
        status, raw = err.code, err.read().decode()
    try:
        return status, json.loads(raw)
    except ValueError:
        return status, raw


def new_device():
    """Register a fresh device and return its (device_id, device token, agent token)."""
    digits = f"{secrets.randbelow(10**9):09d}"
    device_id = f"AG-{digits[:3]}-{digits[3:6]}-{digits[6:]}"
    status, reg = http("POST", "/api/v1/devices/register", {"device_id": device_id, "name": "Security Test"})
    assert status == 201, reg
    return reg["device_id"], reg["auth_token"], reg["agent_token"]


async def recv_json(ws, timeout=3.0):
    return json.loads(await asyncio.wait_for(ws.recv(), timeout=timeout))


async def drain(ws, seconds=0.5):
    out = []
    try:
        while True:
            out.append(json.loads(await asyncio.wait_for(ws.recv(), timeout=seconds)))
    except (asyncio.TimeoutError, websockets.exceptions.ConnectionClosed):
        pass
    return out


async def close_code(ws, timeout=3.0):
    """Wait for the server to close `ws` and return the close code."""
    try:
        while True:
            await asyncio.wait_for(ws.recv(), timeout=timeout)
    except websockets.exceptions.ConnectionClosed as closed:
        return closed.rcvd.code if closed.rcvd else None
    except asyncio.TimeoutError:
        return None


async def connect_agent(device_id, agent_token):
    """Connect a fake agent that authenticates like the real one."""
    ws = await websockets.connect(f"{WS_BASE}/ws/agent/{device_id}")
    await ws.send(json.dumps({"type": "agent_info", "token": agent_token, "device_id": device_id, "has_input": True}))
    welcome = await recv_json(ws)
    assert welcome.get("type") == "agent_connected", welcome
    return ws


async def register_host(device_id, token):
    """Try to register as host; return (socket, first reply)."""
    ws = await websockets.connect(f"{WS_BASE}/ws/{device_id}")
    await ws.send(json.dumps({"type": "register", "role": "host", "host_token": token}))
    return ws, await recv_json(ws)


# ─── 1. REST dispatch to the agent ────────────────────────────────────────────

async def test_rest_agent_dispatch_requires_device_token():
    device_id, device_token, agent_token = new_device()
    agent = await connect_agent(device_id, agent_token)
    try:
        status, _ = http("POST", f"/api/v1/agent/{device_id}/terminal", {"command": "id"})
        assert status in (404, 405), f"REST agent proxy still routes requests: {status}"
        status, _ = http("POST", f"/api/v1/agent/{device_id}/fs/list", {"path": "/"})
        assert status in (404, 405), f"REST agent proxy still routes requests: {status}"

        for token in (None, "", "wrong-token", agent_token):
            body = {"command": "id", "device_id": device_id}
            if token is not None:
                body["auth_token"] = token
            status, reply = http("POST", "/api/v1/terminal/exec", body)
            assert status == 401, f"terminal/exec accepted token {token!r}: {status} {reply}"

        leaked = await drain(agent)
        assert leaked == [], f"Unauthenticated REST calls reached the agent: {leaked}"

        # The device's own token still works
        async def answer():
            req = await recv_json(agent, timeout=5)
            assert req["type"] == "terminal" and req["command"] == "id", req
            await agent.send(json.dumps({"type": "reply", "reply_to": "terminal", "req_id": req["req_id"],
                                         "stdout": "uid=0\n", "stderr": "", "exit_code": 0}))
        responder = asyncio.create_task(answer())
        status, reply = await asyncio.to_thread(
            http, "POST", "/api/v1/terminal/exec",
            {"command": "id", "device_id": device_id, "auth_token": device_token})
        await responder
        assert status == 200 and reply["stdout"] == "uid=0\n", reply
    finally:
        await agent.close()
    print("✓ REST agent dispatch is gone and terminal/exec needs the device token")


# ─── 2. Host registration on the signaling room ───────────────────────────────

async def test_signaling_host_requires_valid_token():
    device_id, device_token, agent_token = new_device()
    agent = await connect_agent(device_id, agent_token)
    try:
        # No token, a wrong token, and the agent token (which must not grant host) are all refused
        for token in ("", "not-the-device-token", agent_token):
            ws, reply = await register_host(device_id, token)
            assert reply.get("type") == "error", f"Host registered with token {token!r}: {reply}"
            assert await close_code(ws) == 4403
            # Even if the socket were still open, nothing it sends may reach the agent
            try:
                await ws.send(json.dumps({"type": "agent_control", "data": {"type": "terminal", "command": "id", "req_id": "x"}}))
            except websockets.exceptions.ConnectionClosed:
                pass

        # Room not backed by a session hash (unknown AG- code) is refused too
        ws, reply = await register_host("AG-000-000-001", "anything")
        assert reply.get("type") == "error", f"Host registered in an unknown AG- room: {reply}"
        await ws.close()

        leaked = await drain(agent)
        assert leaked == [], f"Rejected host reached the agent: {leaked}"

        # The real device token registers and can issue agent requests
        ws, reply = await register_host(device_id, device_token)
        assert reply == {"type": "registered", "role": "host"}, reply
        await ws.send(json.dumps({"type": "agent_control", "data": {"type": "list", "path": "/", "req_id": "ok"}}))
        req = await recv_json(agent)
        assert req.get("type") == "list" and req.get("req_id") == "ok", req
        await ws.close()
    finally:
        await agent.close()
    print("✓ Host registration needs the device token; AG- rooms no longer bypass it")


# ─── 3. Agent's local HTTP server ─────────────────────────────────────────────

def load_agent_module():
    """Import the served agent without its input drivers, so it can never inject input here."""
    sys.modules.setdefault("pynput", types.ModuleType("pynput"))  # stops auto_install and the driver import
    spec = importlib.util.spec_from_file_location("companion_agent_under_test", AGENT_COPIES[0])
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.HAS_PYNPUT = module.HAS_XDOTOOL = False
    for name in ("execute_mouse", "execute_key", "execute_clipboard", "execute_terminal",
                 "execute_fs_list", "execute_fs_read_chunk", "execute_fs_write_chunk",
                 "execute_fs_delete", "execute_fs_mkdir", "release_all_inputs"):
        setattr(module, name, lambda *a, **k: {"status": "recorded"})
    return module


def port_open(port):
    with socket.socket() as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) == 0


async def test_agent_has_no_local_http_server():
    copies = [p for p in AGENT_COPIES if os.path.exists(p)]
    sources = {open(p, "rb").read() for p in copies}
    assert len(sources) == 1, f"Agent copies differ: {copies}"
    source = sources.pop().decode()
    for marker in ("http.server", "HTTPServer", "Access-Control-Allow-Origin", "Allow-Private-Network", ".bind(", ".listen("):
        assert marker not in source, f"Agent still contains a local server ({marker!r})"

    assert not port_open(8765), "Something is already listening on 8765; cannot check the agent"
    agent = load_agent_module()
    assert not hasattr(agent, "CompanionHandler") and not hasattr(agent, "start_http_server")

    device_id, _, agent_token = new_device()
    task = asyncio.create_task(agent.run_websocket_client(BASE_URL, device_id, agent_token))
    try:
        for _ in range(50):
            if http("GET", f"/api/v1/devices/{device_id}/agent_status")[1].get("agent_online"):
                break
            await asyncio.sleep(0.1)
        else:
            raise AssertionError("Real agent did not come online with its token")
        assert not port_open(8765), "Running agent listens on 127.0.0.1:8765"
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
    print(f"✓ Agent opens no local HTTP server ({len(copies)} identical copies checked)")


# ─── 4. Agent impersonation ───────────────────────────────────────────────────

async def test_agent_socket_requires_agent_token():
    device_id, device_token, agent_token = new_device()
    _, _, other_agent_token = new_device()

    attempts = [
        None,                                              # says nothing
        {"type": "agent_info", "device_id": device_id},    # no token
        {"type": "agent_info", "token": "forged"},
        {"type": "agent_info", "token": device_token},     # device token is not the agent token
        {"type": "agent_info", "token": other_agent_token},  # another device's agent token
    ]
    for first in attempts:
        ws = await websockets.connect(f"{WS_BASE}/ws/agent/{device_id}")
        if first is not None:
            await ws.send(json.dumps(first))
        code = await close_code(ws, timeout=15)
        assert code == 4401, f"Impersonated agent {first} was not rejected (close={code})"

    status, presence = http("GET", f"/api/v1/devices/{device_id}/agent_status")
    assert presence["agent_online"] is False, presence
    _, info = http("GET", f"/api/v1/devices/{device_id}/system_info")
    assert info["info"] == {}, f"Impersonated agent wrote agent_info: {info}"

    # An impersonator connected alongside the real agent never sees the controller's input
    real = await connect_agent(device_id, agent_token)
    fake = await websockets.connect(f"{WS_BASE}/ws/agent/{device_id}")
    await fake.send(json.dumps({"type": "agent_info", "token": "forged"}))
    host, reply = await register_host(device_id, device_token)
    assert reply.get("type") == "registered", reply
    await host.send(json.dumps({"type": "agent_control", "data": {"type": "get_home", "req_id": "h1"}}))
    assert (await recv_json(real)).get("req_id") == "h1"
    fake_saw = await drain(fake)
    assert all(m.get("type") == "error" for m in fake_saw), f"Impersonated agent received traffic: {fake_saw}"

    _, info = http("GET", f"/api/v1/devices/{device_id}/system_info")
    assert "token" not in info["info"], "Agent token was stored in the public agent_info"

    # The real agent gives up instead of retrying forever when its token is rejected
    agent = load_agent_module()
    await asyncio.wait_for(agent.run_websocket_client(BASE_URL, device_id, "forged"), timeout=15)

    for ws in (real, fake, host):
        await ws.close()
    print("✓ /ws/agent requires the device's agent token; impersonators get nothing")


# ─── Device ID takeover through re-registration ───────────────────────────────

async def test_register_cannot_take_over_existing_device():
    device_id, device_token, agent_token = new_device()

    for token in (None, "attacker-chosen-token"):
        body = {"device_id": device_id, "name": "Attacker"}
        if token:
            body["auth_token"] = token
        status, reply = http("POST", "/api/v1/devices/register", body)
        assert status == 400, f"Existing Device ID re-registered with token {token!r}: {status} {reply}"

    # The owner's credentials still work, and re-registering with them keeps the same tokens
    status, _ = http("POST", "/api/v1/devices/heartbeat", {"device_id": device_id, "auth_token": device_token})
    assert status == 200
    status, reply = http("POST", "/api/v1/devices/register", {"device_id": device_id, "auth_token": device_token})
    assert status == 201 and reply["device_id"] == device_id and reply["agent_token"] == agent_token, reply
    print("✓ An existing Device ID cannot be re-registered without its token")


async def main():
    await test_rest_agent_dispatch_requires_device_token()
    await test_signaling_host_requires_valid_token()
    await test_agent_has_no_local_http_server()
    await test_agent_socket_requires_agent_token()
    await test_register_cannot_take_over_existing_device()
    print("\n>>> ALL AGENT SECURITY TESTS PASSED! <<<")


if __name__ == "__main__":
    asyncio.run(main())
