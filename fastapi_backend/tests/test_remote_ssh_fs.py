import asyncio
import json
import os
import websockets
import httpx

BASE_HTTP = os.environ.get("BASE_URL", "http://localhost:8000")
BASE_WS = BASE_HTTP.replace("http://", "ws://").replace("https://", "wss://")
# Fixed so reruns recover the same device instead of being refused
DEVICE_TOKEN = "remote-ssh-fs-device-token"

async def test_system_info_and_agent_dispatch():
    device_id = "AG-816-555-726"

    print("--- [TEST 1] Testing /api/v1/terminal/exec security protection ---")
    async with httpx.AsyncClient(base_url=BASE_HTTP) as client:
        res = await client.post("/api/v1/devices/register", json={"device_id": device_id, "auth_token": DEVICE_TOKEN})
        assert res.status_code == 201, res.text
        agent_token = res.json()["agent_token"]

        # Test 1a: Calling without device_id
        res = await client.post("/api/v1/terminal/exec", json={"command": "whoami"})
        data = res.json()
        assert "Target device_id must be specified" in data["stderr"], f"Failed: {data}"
        print("✓ Terminal endpoint correctly rejected execution without remote device_id!")

        # Test 1b: Calling with offline device_id
        res = await client.post("/api/v1/terminal/exec", json={"command": "whoami", "device_id": device_id, "auth_token": DEVICE_TOKEN})
        data = res.json()
        assert f"Remote companion agent for {device_id} is offline" in data["stderr"], f"Failed: {data}"
        print("✓ Terminal endpoint correctly rejected execution when remote agent offline!")

    print("\n--- [TEST 2] Testing Companion Agent Connect & System Metadata ---")
    agent_ws_url = f"{BASE_WS}/ws/agent/{device_id}"
    async with websockets.connect(agent_ws_url) as agent_ws:
        # Send agent_info, authenticated with the agent token
        await agent_ws.send(json.dumps({
            "type": "agent_info",
            "token": agent_token,
            "device_id": device_id,
            "username": "remote_ubuntu",
            "hostname": "remote-laptop",
            "os_name": "Linux",
            "os_version": "5.15.0-generic",
            "platform": "linux",
            "lan_ips": ["192.168.1.105"],
            "primary_ip": "192.168.1.105",
            "default_cwd": "/home/remote_ubuntu",
            "ssh_running": True,
            "has_input": True,
        }))
        init_greeting = json.loads(await agent_ws.recv())
        assert init_greeting["type"] == "agent_connected", init_greeting
        await asyncio.sleep(0.2)

        # Check /api/v1/devices/{device_id}/system_info
        async with httpx.AsyncClient(base_url=BASE_HTTP) as client:
            res = await client.get(f"/api/v1/devices/{device_id}/system_info",
                                   headers={"Authorization": f"Bearer {DEVICE_TOKEN}"})
            info_data = res.json()
            assert info_data["agent_online"] is True
            assert info_data["info"]["username"] == "remote_ubuntu"
            assert info_data["info"]["primary_ip"] == "192.168.1.105"
            print(f"✓ System info verified: {info_data['info']['username']}@{info_data['info']['hostname']} ({info_data['info']['primary_ip']})")

        print("\n--- [TEST 3] Testing Remote Terminal Dispatch & Reply ---")
        # In background, test dispatching a terminal command
        async def mock_agent_listener():
            msg = await agent_ws.recv()
            cmd_data = json.loads(msg)
            assert cmd_data["type"] == "terminal"
            assert cmd_data["command"] == "whoami"
            req_id = cmd_data.get("req_id")
            # Reply
            await agent_ws.send(json.dumps({
                "type": "reply",
                "reply_to": "terminal",
                "req_id": req_id,
                "stdout": "remote_ubuntu\n",
                "stderr": "",
                "exit_code": 0,
                "cwd": "/home/remote_ubuntu",
            }))

        listener_task = asyncio.create_task(mock_agent_listener())

        async with httpx.AsyncClient(base_url=BASE_HTTP) as client:
            res = await client.post("/api/v1/terminal/exec", json={"command": "whoami", "device_id": device_id, "auth_token": DEVICE_TOKEN})
            result = res.json()
            assert result["stdout"] == "remote_ubuntu\n"
            print("✓ Remote command dispatched and executed on target remote machine via agent!")

        await listener_task

    print("\n--- [TEST 4] Testing SSH WebSocket target association ---")
    ssh_ws_url = f"{BASE_WS}/ws/ssh/{device_id}"
    async with websockets.connect(ssh_ws_url) as ssh_ws:
        await ssh_ws.send(json.dumps({"type": "auth", "token": DEVICE_TOKEN}))
        greeting = await ssh_ws.recv()
        greeting_data = json.loads(greeting)
        assert greeting_data["type"] == "target_info"
        assert greeting_data["is_remote"] is True
        assert greeting_data["device_id"] == device_id
        print(f"✓ SSH WebSocket successfully locked to target remote device {device_id} (is_remote=True)!")

    print("\n=======================================================")
    print(">>> ALL REMOTE SSH & AGENT DISPATCH TESTS PASSED! <<<")
    print("=======================================================")

if __name__ == "__main__":
    asyncio.run(test_system_info_and_agent_dispatch())
