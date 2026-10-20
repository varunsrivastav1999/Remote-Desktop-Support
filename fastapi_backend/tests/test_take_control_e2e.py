import asyncio
import json
import os
import urllib.request
import websockets

BASE_URL = os.environ.get("BASE_URL", "http://127.0.0.1:8000")
WS_BASE = BASE_URL.replace("http://", "ws://").replace("https://", "wss://")
SESSION_CODE = "AG-TEST-CONTROL-88"
NORM_ID = "AGTESTCONTROL88"
# Fixed so reruns recover the same device instead of being refused
DEVICE_TOKEN = "e2e-take-control-device-token"

INPUT_EVENTS = [
    {"type": "mousemove", "x": 0.45, "y": 0.65},
    {"type": "mousedown", "x": 0.45, "y": 0.65, "button": 0},
    {"type": "mouseup", "x": 0.45, "y": 0.65, "button": 0},
    {"type": "dblclick", "x": 0.45, "y": 0.65, "button": 0},
    {"type": "contextmenu", "x": 0.50, "y": 0.50, "button": 2},
    {"type": "scroll", "deltaX": 0, "deltaY": -120},
    {"type": "keydown", "key": "Control"},
    {"type": "keydown", "key": "c"},
    {"type": "keyup", "key": "c"},
    {"type": "keyup", "key": "Control"},
]
INPUT_TYPES = {ev["type"] for ev in INPUT_EVENTS}


async def drain(ws, seconds=0.4):
    """Collect every message that arrives within `seconds` of the previous one."""
    out = []
    try:
        while True:
            out.append(json.loads(await asyncio.wait_for(ws.recv(), timeout=seconds)))
    except asyncio.TimeoutError:
        pass
    return out


async def wait_for(ws, predicate, timeout=3.0):
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    seen = []
    while loop.time() < deadline:
        try:
            msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=deadline - loop.time()))
        except asyncio.TimeoutError:
            break
        seen.append(msg)
        if predicate(msg):
            return msg
    raise AssertionError(f"Expected message not received. Saw: {seen}")


def register_device(device_id, auth_token):
    req = urllib.request.Request(
        f"{BASE_URL}/api/v1/devices/register",
        data=json.dumps({"device_id": device_id, "auth_token": auth_token, "name": "Laptop B"}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode())


async def test_full_take_control_pipeline():
    print("\n[TEST] 1. Registering Device and Companion Agent on Remote Laptop B...")
    registration = register_device(SESSION_CODE, DEVICE_TOKEN)
    assert registration["device_id"] == SESSION_CODE, registration
    agent_ws_url = f"{WS_BASE}/ws/agent/{SESSION_CODE}"

    received_events_on_remote_b = []
    agent_connected_event = asyncio.Event()

    async def run_fake_remote_agent_b():
        async with websockets.connect(agent_ws_url) as ws:
            # Send agent info for Laptop B; it carries the agent token that authenticates it
            await ws.send(json.dumps({
                "type": "agent_info",
                "token": registration["agent_token"],
                "device_id": SESSION_CODE,
                "username": "remote_user_b",
                "hostname": "laptop-b-system",
                "os_name": "Linux",
                "primary_ip": "192.168.1.185",
                "ssh_running": True,
                "has_input": True,
            }))
            welcome = json.loads(await ws.recv())
            assert welcome.get("type") == "agent_connected", welcome
            agent_connected_event.set()

            async for raw in ws:
                data = json.loads(raw)
                received_events_on_remote_b.append(data)
                mtype = data.get("type")
                req_id = data.get("req_id")

                if mtype == "take_control":
                    await ws.send(json.dumps({"type": "control_granted", "req_id": req_id}))
                elif mtype == "release_control":
                    await ws.send(json.dumps({"type": "control_released", "req_id": req_id}))
                elif mtype == "list":
                    await ws.send(json.dumps({
                        "type": "reply",
                        "reply_to": "listing",
                        "req_id": req_id,
                        "entries": [{"name": "document.txt", "path": "/home/user/document.txt", "is_dir": False, "size": 1024}],
                    }))

    def agent_types():
        return [e.get("type") for e in received_events_on_remote_b]

    agent_task = asyncio.create_task(run_fake_remote_agent_b())
    await asyncio.wait_for(agent_connected_event.wait(), timeout=5.0)
    await asyncio.sleep(0.2)
    print(" -> Remote Companion Agent on Laptop B connected!")

    # 2. Check system info endpoint from Controller
    print("[TEST] 2. Controller Laptop A verifying remote device info...")
    req = urllib.request.Request(f"{BASE_URL}/api/v1/devices/{SESSION_CODE}/system_info")
    with urllib.request.urlopen(req) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode())
        assert data.get("agent_online") is True
        info = data.get("info", {})
        assert info.get("hostname") == "laptop-b-system"
        assert info.get("username") == "remote_user_b"
        print(" -> Verified! Remote system is laptop-b-system (192.168.1.185)")

    with urllib.request.urlopen(f"{BASE_URL}/api/v1/devices/{SESSION_CODE}/agent_status") as resp:
        status = json.loads(resp.read().decode())
        assert status.get("agent_online") is True and status.get("has_input") is True, status
        print(" -> Agent presence reports input capability for the host's grant decision")

    # 3. Host (browser host on Laptop B) and Controller Laptop A join the signaling room
    print("[TEST] 3. Host Laptop B and Controller Laptop A joining the Signaling Room...")
    host_ws = await websockets.connect(f"{WS_BASE}/ws/{SESSION_CODE}")
    await host_ws.send(json.dumps({"type": "register", "role": "host", "host_token": DEVICE_TOKEN}))
    await wait_for(host_ws, lambda m: m.get("type") == "registered")

    client_ws = await websockets.connect(f"{WS_BASE}/ws/{SESSION_CODE}")
    await client_ws.send(json.dumps({
        "type": "register",
        "role": "client",
        "client_device_id": "CONTROLLER-LAPTOP-A",
        "caller_name": "Admin Controller",
    }))
    await wait_for(client_ws, lambda m: m.get("type") == "registered")
    await drain(host_ws, 0.3)
    await drain(client_ws, 0.3)
    print(" -> Both peers registered in signaling room!")

    # 4. View Only: input and agent requests from the controller must not reach Laptop B
    print("[TEST] 4. Verifying View Only mode blocks remote input before Take Control...")
    received_events_on_remote_b.clear()
    for ev in INPUT_EVENTS[:2] + [{"type": "terminal", "command": "id", "req_id": "sneaky"}]:
        await client_ws.send(json.dumps({"type": "agent_control", "data": ev}))
    await asyncio.sleep(0.4)
    assert received_events_on_remote_b == [], f"Agent received input without control: {received_events_on_remote_b}"
    print(" -> No input or agent request reached Laptop B in View Only mode")

    # 5. Controller clicks "Take Control"; the host is the authority and grants it
    print("[TEST] 5. Controller Laptop A triggering 'Take Control'...")
    await client_ws.send(json.dumps({"type": "control_event", "data": {"type": "take_control", "seq": 1}}))
    request = await wait_for(host_ws, lambda m: m.get("type") == "take_control")
    assert request.get("seq") == 1
    assert "take_control" not in agent_types(), "Agent must not be armed before the host grants control"

    await host_ws.send(json.dumps({"type": "control_granted", "seq": 1, "input_route": "agent"}))
    granted = await wait_for(client_ws, lambda m: m.get("type") == "control_granted")
    assert granted.get("seq") == 1 and granted.get("input_route") == "agent", granted
    await asyncio.sleep(0.3)
    assert "take_control" in agent_types(), "Agent was not armed after the host granted control"
    print(" -> Take Control granted by host Laptop B and companion agent armed!")

    # 6. Controller sends interactive input events
    print("[TEST] 6. Sending mouse movement, clicks, and keyboard events...")
    received_events_on_remote_b.clear()
    await drain(host_ws, 0.2)
    for ev in INPUT_EVENTS:
        await client_ws.send(json.dumps({"type": "agent_control", "data": ev}))
    await asyncio.sleep(0.5)

    assert agent_types() == [ev["type"] for ev in INPUT_EVENTS], \
        f"Input events not delivered exactly once, in order: {agent_types()}"
    host_input = [m for m in await drain(host_ws, 0.3)
                  if (m.get("data") or {}).get("type") in INPUT_TYPES or m.get("type") in INPUT_TYPES]
    assert host_input == [], f"Agent-bound input was also relayed to the host peer: {host_input}"
    print(f" -> All {len(INPUT_EVENTS)} input events delivered once to Laptop B (none duplicated to host)!")

    # 7. Release Control
    print("[TEST] 7. Releasing control...")
    await client_ws.send(json.dumps({"type": "release_control", "seq": 2}))
    request = await wait_for(host_ws, lambda m: m.get("type") == "release_control")
    assert request.get("seq") == 2
    await asyncio.sleep(0.3)
    assert "release_control" in agent_types()
    await host_ws.send(json.dumps({"type": "control_released", "seq": 2}))
    released = await wait_for(client_ws, lambda m: m.get("type") == "control_released")
    assert released.get("seq") == 2

    received_events_on_remote_b.clear()
    await client_ws.send(json.dumps({"type": "agent_control", "data": INPUT_EVENTS[0]}))
    await asyncio.sleep(0.4)
    assert received_events_on_remote_b == [], f"Input still delivered after release: {received_events_on_remote_b}"
    print(" -> Control released on Laptop B and input blocked again!")

    # 8. Controller disconnects while holding control: agent must release held input
    print("[TEST] 8. Controller dropping mid-control releases held input on Laptop B...")
    await client_ws.send(json.dumps({"type": "control_event", "data": {"type": "take_control", "seq": 3}}))
    await wait_for(host_ws, lambda m: m.get("type") == "take_control")
    await host_ws.send(json.dumps({"type": "control_granted", "seq": 3, "input_route": "agent"}))
    await wait_for(client_ws, lambda m: m.get("type") == "control_granted")
    await asyncio.sleep(0.2)
    received_events_on_remote_b.clear()
    await client_ws.close()
    await asyncio.sleep(0.5)
    assert "release_control" in agent_types(), f"Agent not released on controller disconnect: {agent_types()}"
    print(" -> Companion agent released input when the controller disconnected!")
    await host_ws.close()

    # 9. Test SSH loopback protection
    print("[TEST] 9. Verifying SSH loopback rejection...")
    ssh_url = f"{WS_BASE}/ws/ssh/{SESSION_CODE}"
    async with websockets.connect(ssh_url) as ssh_ws:
        init_info = json.loads(await ssh_ws.recv())
        assert init_info.get("type") == "target_info"
        assert init_info.get("is_remote") is True
        assert init_info.get("hostname") == "laptop-b-system"

        # Try to connect to localhost (should be blocked!)
        await ssh_ws.send(json.dumps({
            "type": "connect",
            "host": "127.0.0.1",
            "port": 22,
            "username": "root",
            "password": "testpassword",
        }))

        err_msg = json.loads(await ssh_ws.recv())
        assert err_msg.get("type") == "error"
        assert "forbidden" in err_msg.get("message").lower()
        print(" -> SSH loopback connection to localhost correctly rejected!")

    agent_task.cancel()
    print("\n[SUCCESS] ALL END-TO-END REMOTE CONTROL & SSH CHECKS PASSED!\n")

if __name__ == "__main__":
    asyncio.run(test_full_take_control_pipeline())
