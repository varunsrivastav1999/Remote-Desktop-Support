import asyncio
import json
import logging
import threading
from typing import Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.services.device_service import normalize_device_id

router = APIRouter(tags=["ssh"])
logger = logging.getLogger("remote_support.ssh")

try:
    import paramiko
    HAS_PARAMIKO = True
except ImportError:
    HAS_PARAMIKO = False


@router.websocket("/ws/ssh/{device_id}")
async def ssh_websocket_endpoint(websocket: WebSocket, device_id: str):
    """
    Direct interactive SSH session bridged over WebSocket to the remote connected laptop.
    Ensures SSH always connects to the remote device, never the local client.
    """
    await websocket.accept()
    norm_id = normalize_device_id(device_id)
    redis_client = websocket.app.state.redis

    # Auto-detect remote device IP and system info
    raw_info = await redis_client.hgetall(f"device:{norm_id}:agent_info")
    remote_info = {}
    for k, v in (raw_info or {}).items():
        try:
            remote_info[k] = json.loads(v)
        except Exception:
            remote_info[k] = v

    detected_ip = remote_info.get("primary_ip") or (remote_info.get("lan_ips", [""])[0] if isinstance(remote_info.get("lan_ips"), list) else None)
    detected_user = remote_info.get("username", "")

    # Send target association handshake
    await websocket.send_json({
        "type": "target_info",
        "device_id": norm_id,
        "is_remote": True,
        "detected_ip": detected_ip,
        "detected_user": detected_user,
        "hostname": remote_info.get("hostname", ""),
        "os_name": remote_info.get("os_name", ""),
        "ssh_running": remote_info.get("ssh_running", False),
    })

    if not HAS_PARAMIKO:
        await websocket.send_json({
            "type": "error",
            "message": "Paramiko SSH engine is not installed on server. Use Remote Agent Shell mode or install paramiko.",
        })
        await websocket.close(code=1011)
        return

    client: Optional[paramiko.SSHClient] = None
    channel = None
    stop_event = threading.Event()
    loop = asyncio.get_running_loop()

    def read_from_channel(chan, ws_loop, ws):
        while not stop_event.is_set():
            try:
                if chan.recv_ready():
                    data = chan.recv(4096)
                    if not data:
                        break
                    text = data.decode("utf-8", errors="replace")
                    asyncio.run_coroutine_threadsafe(ws.send_text(text), ws_loop)
                else:
                    chan.settimeout(0.1)
                    try:
                        data = chan.recv(4096)
                        if data:
                            text = data.decode("utf-8", errors="replace")
                            asyncio.run_coroutine_threadsafe(ws.send_text(text), ws_loop)
                    except Exception:
                        pass
            except Exception:
                break
        stop_event.set()

    try:
        # Wait for connection credentials message
        init_raw = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
        init_data = json.loads(init_raw)

        if init_data.get("type") != "connect":
            await websocket.send_json({"type": "error", "message": "Expected connect message with credentials."})
            await websocket.close()
            return

        target_host = init_data.get("host") or detected_ip
        target_port = int(init_data.get("port") or 22)
        username = init_data.get("username") or detected_user
        password = init_data.get("password")
        key_data = init_data.get("private_key")

        # Strictly forbid localhost or container internal loopback
        if str(target_host).lower() in ("localhost", "127.0.0.1", "::1", "0.0.0.0", "host.docker.internal"):
            await websocket.send_json({
                "type": "error",
                "message": "Local loopback connections are strictly forbidden. SSH must connect to the remote device.",
            })
            await websocket.close()
            return

        if not target_host:
            await websocket.send_json({
                "type": "error",
                "message": f"No IP address detected for remote device {norm_id}. Ensure companion agent or host is online.",
            })
            await websocket.close()
            return

        await websocket.send_json({
            "type": "status",
            "message": f"Connecting to remote SSH at {username}@{target_host}:{target_port} (Device {norm_id})...",
        })

        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        # Connect in a separate thread to avoid blocking asyncio loop
        def do_connect():
            client.connect(
                hostname=target_host,
                port=target_port,
                username=username,
                password=password or None,
                timeout=10,
                banner_timeout=10,
                auth_timeout=10,
                look_for_keys=False,
                allow_agent=False,
            )

        try:
            await asyncio.to_thread(do_connect)
        except Exception as conn_err:
            await websocket.send_json({
                "type": "error",
                "message": f"SSH connection to remote host {target_host}:{target_port} failed: {conn_err}. (Tip: If port 22 is firewalled, use the WebRTC Remote Shell tab).",
            })
            await websocket.close()
            return

        channel = client.invoke_shell(term="xterm-256color", width=100, height=30)
        channel.settimeout(0.0)

        reader_thread = threading.Thread(target=read_from_channel, args=(channel, loop, websocket), daemon=True)
        reader_thread.start()

        await websocket.send_json({
            "type": "connected",
            "target": f"{username}@{target_host}:{target_port}",
            "device_id": norm_id,
            "hostname": remote_info.get("hostname", ""),
            "os_name": remote_info.get("os_name", ""),
        })

        banner = (
            f"\r\n\x1b[1;32m════════════════════════════════════════════════════════════════════\x1b[0m\r\n"
            f"  \x1b[1;32mCONNECTED TO REMOTE DEVICE: \x1b[1;33m{norm_id}\x1b[0m\r\n"
            f"  \x1b[1;37m• Remote Target: \x1b[1;36m{username}@{target_host}:{target_port}\x1b[0m\r\n"
            f"  \x1b[1;37m• Hostname:      \x1b[1;34m{remote_info.get('hostname', 'Remote System')}\x1b[0m\r\n"
            f"  \x1b[1;37m• Remote OS:     \x1b[1;35m{remote_info.get('os_name', 'Remote System')}\x1b[0m\r\n"
            f"\x1b[1;32m════════════════════════════════════════════════════════════════════\x1b[0m\r\n"
        )
        await websocket.send_text(banner)

        while not stop_event.is_set():
            msg = await websocket.receive_text()
            try:
                parsed = json.loads(msg)
                if parsed.get("type") == "resize":
                    cols = int(parsed.get("cols", 80))
                    rows = int(parsed.get("rows", 24))
                    channel.resize_pty(width=cols, height=rows)
                    continue
            except Exception:
                pass

            # Raw terminal input
            if channel and not channel.closed:
                channel.send(msg)

    except WebSocketDisconnect:
        pass
    except asyncio.TimeoutError:
        try:
            await websocket.send_json({"type": "error", "message": "Connection setup timed out after 30 seconds."})
            await websocket.close()
        except Exception:
            pass
    except Exception as e:
        logger.error(f"SSH WebSocket error: {e}")
        try:
            await websocket.send_json({"type": "error", "message": f"SSH error: {e}"})
            await websocket.close()
        except Exception:
            pass
    finally:
        stop_event.set()
        if channel:
            try:
                channel.close()
            except Exception:
                pass
        if client:
            try:
                client.close()
            except Exception:
                pass
