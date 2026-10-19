import asyncio
import json
import urllib.request
import websockets

BASE_URL = "http://127.0.0.1:8000"
WS_BASE = "ws://127.0.0.1:8000"
SESSION_CODE = "AG-TEST-CONTROL-88"
NORM_ID = "AGTESTCONTROL88"

async def test_full_take_control_pipeline():
    print("\n[TEST] 1. Registering Device and Companion Agent on Remote Laptop B...")
    agent_ws_url = f"{WS_BASE}/ws/agent/{SESSION_CODE}"

    received_events_on_remote_b = []
    agent_connected_event = asyncio.Event()

    async def run_fake_remote_agent_b():
        async with websockets.connect(agent_ws_url) as ws:
            # Receive welcome
            msg = await ws.recv()
            welcome = json.loads(msg)
            assert welcome.get("type") == "agent_connected"
            agent_connected_event.set()

            # Send agent info for Laptop B
            await ws.send(json.dumps({
                "type": "agent_info",
                "device_id": SESSION_CODE,
                "username": "remote_user_b",
                "hostname": "laptop-b-system",
                "os_name": "Linux",
                "primary_ip": "192.168.1.185",
                "ssh_running": True,
            }))

            async for raw in ws:
                data = json.loads(raw)
                received_events_on_remote_b.append(data)
                mtype = data.get("type")
                req_id = data.get("req_id")

                if mtype == "take_control":
                    # Remote Laptop B grants control!
                    await ws.send(json.dumps({
                        "type": "control_granted",
                        "status": "granted",
                        "req_id": req_id,
                    }))
                elif mtype == "release_control":
                    await ws.send(json.dumps({
                        "type": "control_released",
                        "status": "released",
                        "req_id": req_id,
                    }))
                elif mtype == "list":
                    await ws.send(json.dumps({
                        "type": "reply",
                        "reply_to": "listing",
                        "req_id": req_id,
                        "entries": [{"name": "document.txt", "path": "/home/user/document.txt", "is_dir": False, "size": 1024}],
                    }))

    agent_task = asyncio.create_task(run_fake_remote_agent_b())
    await asyncio.wait_for(agent_connected_event.wait(), timeout=5.0)
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

    # 3. Controller Laptop A connects to Signaling WebSocket
    print("[TEST] 3. Controller Laptop A connecting to Signaling Room...")
    controller_ws_url = f"{WS_BASE}/ws/{SESSION_CODE}"
    client_received_messages = []

    async with websockets.connect(controller_ws_url) as client_ws:
        # Register as client
        await client_ws.send(json.dumps({
            "type": "register",
            "role": "client",
            "client_device_id": "CONTROLLER-LAPTOP-A",
            "caller_name": "Admin Controller",
        }))

        reg_ack = json.loads(await client_ws.recv())
        assert reg_ack.get("type") == "registered"
        print(" -> Controller Laptop A registered in signaling room!")

        # 4. Controller clicks "Take Control"
        print("[TEST] 4. Controller Laptop A triggering 'Take Control'...")
        await client_ws.send(json.dumps({
            "type": "agent_control",
            "data": {"type": "take_control", "req_id": "test_take_1"},
        }))

        # Wait for control_granted
        granted = False
        for _ in range(10):
            try:
                msg = await asyncio.wait_for(client_ws.recv(), timeout=2.0)
                parsed = json.loads(msg)
                client_received_messages.append(parsed)
                if parsed.get("type") == "control_granted" or parsed.get("status") == "granted":
                    granted = True
                    break
            except asyncio.TimeoutError:
                break

        assert granted, f"Take Control was not granted! Received: {client_received_messages}"
        print(" -> Take Control successfully granted by remote Laptop B!")

        # 5. Controller Laptop A sends interactive input events
        print("[TEST] 5. Sending mouse movement, clicks, and keyboard events...")
        test_events = [
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

        for ev in test_events:
            await client_ws.send(json.dumps({
                "type": "agent_control",
                "data": ev,
            }))

        await asyncio.sleep(0.5)

        # Verify Laptop B received all input events
        received_types = [e.get("type") for e in received_events_on_remote_b]
        for ev in test_events:
            assert ev["type"] in received_types, f"Event {ev['type']} was not received by Laptop B! Received: {received_types}"
        print(f" -> All {len(test_events)} input events were delivered to Laptop B's OS input channel!")

        # 6. Release Control
        print("[TEST] 6. Releasing control...")
        await client_ws.send(json.dumps({
            "type": "agent_control",
            "data": {"type": "release_control"},
        }))

        await asyncio.sleep(0.3)
        assert "release_control" in [e.get("type") for e in received_events_on_remote_b]
        print(" -> Control successfully released on Laptop B!")

    # 7. Test SSH loopback protection
    print("[TEST] 7. Verifying SSH loopback rejection...")
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
