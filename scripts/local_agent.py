#!/usr/bin/env python3
"""
Remote Desktop Support — Native Host Companion Agent
Provides native OS mouse, keyboard, terminal, and filesystem control across Linux, macOS, and Windows.
Supports:
  1. Direct Outbound WebSocket connection to Signaling Server (/ws/agent/{device_id}),
     authenticated with the agent token shown on the Host screen (--token)
  2. Native input injection via pynput, Quartz (macOS), Win32 (Windows), and xdotool (Linux)

The agent opens no listening ports: every request reaches it through its authenticated
server connection.
"""

import sys
import os
import json
import base64
import shutil
import argparse
import asyncio
import subprocess

DEFAULT_SERVER = "https://webmaster-meal-classroom-colony.trycloudflare.com"

# ═════════════════════════════════════════════════════════════
# Auto-Install Missing Dependencies
# ═════════════════════════════════════════════════════════════

def auto_install(package_name):
    try:
        __import__(package_name)
    except ImportError:
        try:
            print(f"[*] Installing required helper '{package_name}'...")
            subprocess.run([sys.executable, "-m", "pip", "install", "--quiet", package_name], check=False)
        except Exception:
            pass

auto_install("pynput")
auto_install("websockets")

# ═════════════════════════════════════════════════════════════
# Detect Screen Resolution
# ═════════════════════════════════════════════════════════════

SCREEN_WIDTH = 1920
SCREEN_HEIGHT = 1080

try:
    if sys.platform == "darwin":
        from AppKit import NSScreen
        frame = NSScreen.mainScreen().frame()
        SCREEN_WIDTH = int(frame.size.width)
        SCREEN_HEIGHT = int(frame.size.height)
    elif sys.platform == "win32":
        import ctypes
        user32 = ctypes.windll.user32
        user32.SetProcessDPIAware()
        SCREEN_WIDTH = int(user32.GetSystemMetrics(0))
        SCREEN_HEIGHT = int(user32.GetSystemMetrics(1))
    else:
        # Linux detection
        if shutil.which("xdotool"):
            try:
                out = subprocess.check_output(["xdotool", "getdisplaygeometry"], text=True).strip().split()
                if len(out) == 2:
                    SCREEN_WIDTH, SCREEN_HEIGHT = int(out[0]), int(out[1])
            except Exception:
                pass
        if SCREEN_WIDTH == 1920:
            import tkinter
            root = tkinter.Tk()
            root.withdraw()
            SCREEN_WIDTH = int(root.winfo_screenwidth())
            SCREEN_HEIGHT = int(root.winfo_screenheight())
            root.destroy()
except Exception:
    pass

# ═════════════════════════════════════════════════════════════
# Input Drivers: pynput + Linux xdotool fallback
# ═════════════════════════════════════════════════════════════

HAS_PYNPUT = False
mouse = None
keyboard = None
HAS_XDOTOOL = shutil.which("xdotool") is not None

try:
    from pynput.mouse import Controller as MouseController, Button
    from pynput.keyboard import Controller as KeyboardController, Key
    mouse = MouseController()
    keyboard = KeyboardController()
    HAS_PYNPUT = True
except Exception as e:
    if not HAS_XDOTOOL and sys.platform.startswith("linux"):
        print(f"[Companion Agent Notice] For Linux input control, install xdotool: sudo apt-get install -y xdotool")

KEY_MAP = {}
if HAS_PYNPUT:
    KEY_MAP = {
        "Enter": Key.enter,
        "Return": Key.enter,
        "Backspace": Key.backspace,
        "Tab": Key.tab,
        "Escape": Key.esc,
        "Space": Key.space,
        " ": Key.space,
        "ArrowUp": Key.up,
        "ArrowDown": Key.down,
        "ArrowLeft": Key.left,
        "ArrowRight": Key.right,
        "Shift": Key.shift,
        "ShiftLeft": getattr(Key, "shift_l", Key.shift),
        "ShiftRight": getattr(Key, "shift_r", Key.shift),
        "Control": Key.ctrl,
        "ControlLeft": getattr(Key, "ctrl_l", Key.ctrl),
        "ControlRight": getattr(Key, "ctrl_r", Key.ctrl),
        "Alt": Key.alt,
        "AltLeft": getattr(Key, "alt_l", Key.alt),
        "AltRight": getattr(Key, "alt_r", Key.alt),
        "Meta": Key.cmd,
        "MetaLeft": Key.cmd,
        "MetaRight": Key.cmd,
        "Cmd": Key.cmd,
        "Windows": Key.cmd,
        "Delete": Key.delete,
        "Home": Key.home,
        "End": Key.end,
        "PageUp": Key.page_up,
        "PageDown": Key.page_down,
        "F1": Key.f1,
        "F2": Key.f2,
        "F3": Key.f3,
        "F4": Key.f4,
        "F5": Key.f5,
        "F6": Key.f6,
        "F7": Key.f7,
        "F8": Key.f8,
        "F9": Key.f9,
        "F10": Key.f10,
        "F11": Key.f11,
        "F12": Key.f12,
    }

def run_xdotool(*args):
    try:
        subprocess.run(["xdotool", *args], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass

# ═════════════════════════════════════════════════════════════
# Unified Action Handlers (Mouse, Keyboard, Terminal, FS)
# ═════════════════════════════════════════════════════════════

def execute_mouse(data):
    mtype = data.get("type", "mousemove")
    x_norm = float(data.get("x", 0))
    y_norm = float(data.get("y", 0))
    btn_idx = int(data.get("button", 0))

    target_x = max(0, min(SCREEN_WIDTH - 1, int(x_norm * SCREEN_WIDTH)))
    target_y = max(0, min(SCREEN_HEIGHT - 1, int(y_norm * SCREEN_HEIGHT)))

    if HAS_PYNPUT and mouse:
        try:
            btn = Button.left
            if btn_idx == 1:
                btn = Button.middle
            elif btn_idx == 2 or mtype == "contextmenu":
                btn = Button.right

            if mtype == "mousemove":
                mouse.position = (target_x, target_y)
            elif mtype == "mousedown":
                mouse.position = (target_x, target_y)
                mouse.press(btn)
            elif mtype == "mouseup":
                mouse.position = (target_x, target_y)
                mouse.release(btn)
            elif mtype == "click":
                mouse.position = (target_x, target_y)
                mouse.click(btn, 1)
            elif mtype == "dblclick":
                mouse.position = (target_x, target_y)
                mouse.click(btn, 2)
            elif mtype == "contextmenu":
                mouse.position = (target_x, target_y)
                mouse.click(Button.right, 1)
            elif mtype == "scroll":
                delta_x = int(data.get("deltaX", 0))
                delta_y = int(data.get("deltaY", 0))
                steps_y = -max(1, min(6, abs(int(delta_y / 30)))) if delta_y > 0 else (max(1, min(6, abs(int(delta_y / 30)))) if delta_y < 0 else 0)
                steps_x = -max(1, min(6, abs(int(delta_x / 30)))) if delta_x > 0 else (max(1, min(6, abs(int(delta_x / 30)))) if delta_x < 0 else 0)
                mouse.scroll(steps_x, steps_y)
            return {"status": "ok"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    elif HAS_XDOTOOL:
        try:
            xbtn = "1" if btn_idx == 0 else ("2" if btn_idx == 1 else "3")
            if mtype == "mousemove":
                run_xdotool("mousemove", str(target_x), str(target_y))
            elif mtype == "mousedown":
                run_xdotool("mousemove", str(target_x), str(target_y))
                run_xdotool("mousedown", xbtn)
            elif mtype == "mouseup":
                run_xdotool("mousemove", str(target_x), str(target_y))
                run_xdotool("mouseup", xbtn)
            elif mtype == "click":
                run_xdotool("mousemove", str(target_x), str(target_y))
                run_xdotool("click", xbtn)
            elif mtype == "dblclick":
                run_xdotool("mousemove", str(target_x), str(target_y))
                run_xdotool("click", "--repeat", "2", "1")
            elif mtype == "contextmenu":
                run_xdotool("mousemove", str(target_x), str(target_y))
                run_xdotool("click", "3")
            elif mtype == "scroll":
                delta_y = int(data.get("deltaY", 0))
                run_xdotool("click", "5" if delta_y > 0 else "4")
            return {"status": "ok"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    return {"status": "error", "message": "No input simulation driver available"}


def execute_key(data):
    ktype = data.get("type", "keydown")
    key_str = data.get("key", "")
    if not key_str:
        return {"status": "ok"}

    if HAS_PYNPUT and keyboard:
        try:
            target_key = KEY_MAP.get(key_str, key_str if len(key_str) == 1 else None)
            if target_key:
                if ktype == "keydown":
                    keyboard.press(target_key)
                elif ktype == "keyup":
                    keyboard.release(target_key)
            return {"status": "ok"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    elif HAS_XDOTOOL:
        try:
            if key_str == "Enter": x_key = "Return"
            elif key_str == "Escape": x_key = "Escape"
            elif key_str == "Backspace": x_key = "BackSpace"
            elif key_str == "Control": x_key = "Control_L"
            elif key_str == "Shift": x_key = "Shift_L"
            elif key_str == "Alt": x_key = "Alt_L"
            elif key_str in ("Meta", "Super", "Windows"): x_key = "Super_L"
            elif key_str == "Tab": x_key = "Tab"
            elif key_str == "Delete": x_key = "Delete"
            elif key_str == "Home": x_key = "Home"
            elif key_str == "End": x_key = "End"
            elif key_str == "PageUp": x_key = "Page_Up"
            elif key_str == "PageDown": x_key = "Page_Down"
            elif key_str in (" ", "Space"): x_key = "space"
            elif key_str.startswith("F") and key_str[1:].isdigit(): x_key = key_str
            else: x_key = key_str.lower()

            if ktype == "keydown":
                run_xdotool("keydown", x_key)
            elif ktype == "keyup":
                run_xdotool("keyup", x_key)
            return {"status": "ok"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    return {"status": "error", "message": "No key driver available"}


def execute_clipboard(text):
    """Inject clipboard content directly into the remote OS clipboard."""
    if not text:
        return {"status": "ok"}
    try:
        if sys.platform == "darwin":
            subprocess.run(["pbcopy"], input=text.encode("utf-8"), check=False)
        elif sys.platform == "win32":
            subprocess.run(["clip"], input=text.encode("utf-8"), check=False)
        else:
            if shutil.which("xclip"):
                subprocess.run(["xclip", "-selection", "clipboard"], input=text.encode("utf-8"), check=False)
            elif shutil.which("wl-copy"):
                subprocess.run(["wl-copy"], input=text.encode("utf-8"), check=False)
        return {"status": "ok"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def release_all_inputs():
    """Safety cleanup: release any held mouse buttons or modifier keys on remote host."""
    if HAS_PYNPUT:
        if mouse:
            try:
                mouse.release(Button.left)
                mouse.release(Button.right)
                mouse.release(Button.middle)
            except Exception:
                pass
        if keyboard:
            for k in (
                Key.ctrl, Key.ctrl_l, Key.ctrl_r,
                Key.alt, Key.alt_l, Key.alt_r,
                Key.shift, Key.shift_l, Key.shift_r,
                Key.cmd, Key.cmd_l, Key.cmd_r
            ):
                try:
                    keyboard.release(k)
                except Exception:
                    pass
    elif HAS_XDOTOOL:
        try:
            run_xdotool("mouseup", "1")
            run_xdotool("mouseup", "2")
            run_xdotool("mouseup", "3")
            run_xdotool("keyup", "Control_L", "Control_R", "Alt_L", "Alt_R", "Shift_L", "Shift_R", "Super_L", "Super_R")
        except Exception:
            pass
    return {"status": "ok"}


current_terminal_cwd = os.path.expanduser("~")

def execute_terminal(data):
    global current_terminal_cwd
    cmd = data.get("command", "").strip()
    cwd = data.get("cwd") or current_terminal_cwd
    if not os.path.isdir(cwd):
        cwd = os.path.expanduser("~")
    current_terminal_cwd = cwd

    if not cmd:
        return {"stdout": "", "stderr": "", "exit_code": 0, "cwd": current_terminal_cwd}

    # Built-in cd directory changer
    if cmd == "cd" or cmd == "cd ~":
        current_terminal_cwd = os.path.expanduser("~")
        return {"stdout": "", "stderr": "", "exit_code": 0, "cwd": current_terminal_cwd}
    elif cmd.startswith("cd "):
        target = cmd[3:].strip().strip('"').strip("'")
        target_path = os.path.expanduser(target) if target.startswith("~") else os.path.join(current_terminal_cwd, target)
        target_path = os.path.abspath(target_path)
        if os.path.isdir(target_path):
            current_terminal_cwd = target_path
            return {"stdout": "", "stderr": "", "exit_code": 0, "cwd": current_terminal_cwd}
        else:
            return {"stdout": "", "stderr": f"cd: {target}: No such file or directory\n", "exit_code": 1, "cwd": current_terminal_cwd}

    try:
        if sys.platform == "win32":
            shell_cmd = ["cmd.exe", "/c", cmd]
        else:
            shell_bin = os.environ.get("SHELL", "/bin/sh")
            shell_cmd = [shell_bin, "-c", cmd]

        proc = subprocess.run(
            shell_cmd,
            capture_output=True,
            text=True,
            timeout=15,
            cwd=current_terminal_cwd,
        )
        return {
            "stdout": proc.stdout,
            "stderr": proc.stderr,
            "exit_code": proc.returncode,
            "cwd": current_terminal_cwd,
        }
    except subprocess.TimeoutExpired:
        return {"stdout": "", "stderr": "Command timed out after 15 seconds\n", "exit_code": 124, "cwd": current_terminal_cwd}
    except Exception as e:
        return {"stdout": "", "stderr": f"Execution error: {e}\n", "exit_code": 1, "cwd": current_terminal_cwd}


def execute_fs_home(data=None):
    home = os.path.expanduser("~")
    sep = os.sep
    plat = sys.platform
    return {"path": home, "separator": sep, "platform": plat}


def execute_fs_list(data):
    dir_path = data.get("path") or os.path.expanduser("~")
    try:
        entries = []
        with os.scandir(dir_path) as it:
            for entry in it:
                try:
                    stat = entry.stat(follow_symlinks=False)
                    is_dir = entry.is_dir(follow_symlinks=False)
                    entries.append({
                        "name": entry.name,
                        "path": entry.path,
                        "is_dir": is_dir,
                        "size": 0 if is_dir else stat.st_size,
                    })
                except (PermissionError, OSError):
                    continue

        entries.sort(key=lambda x: (not x["is_dir"], x["name"].lower()))
        return {"path": dir_path, "entries": entries}
    except Exception as e:
        return {"path": dir_path, "entries": [], "error": str(e)}


def execute_fs_read_chunk(data):
    path = data.get("path", "")
    offset = int(data.get("offset", 0))
    chunk_size = int(data.get("size", 48 * 1024))
    try:
        total_size = os.path.getsize(path)
        with open(path, "rb") as f:
            f.seek(offset)
            chunk_data = f.read(chunk_size)
            encoded = base64.b64encode(chunk_data).decode("ascii")
        return {
            "name": os.path.basename(path),
            "data": encoded,
            "size": len(chunk_data),
            "offset": offset,
            "total_size": total_size,
            "eof": (offset + len(chunk_data)) >= total_size,
        }
    except Exception as e:
        return {"error": str(e), "eof": True, "size": 0, "data": ""}


def execute_fs_write_chunk(data):
    dest_dir = data.get("dest", "")
    filename = data.get("name", "")
    chunk_b64 = data.get("data", "")
    offset = int(data.get("offset", 0))
    target_path = os.path.join(dest_dir, filename) if filename else dest_dir
    try:
        raw_bytes = base64.b64decode(chunk_b64)
        mode = "wb" if offset == 0 else "r+b"
        if not os.path.exists(target_path) and offset > 0:
            mode = "wb"
        with open(target_path, mode) as f:
            f.seek(offset)
            f.write(raw_bytes)
        return {"status": "ok", "path": target_path, "written": len(raw_bytes)}
    except Exception as e:
        return {"error": str(e), "status": "error"}


def execute_fs_delete(data):
    target = data.get("path", "")
    try:
        if os.path.isdir(target):
            shutil.rmtree(target)
        elif os.path.isfile(target):
            os.remove(target)
        return {"status": "ok"}
    except Exception as e:
        return {"status": "error", "error": str(e)}


def execute_fs_mkdir(data):
    target = data.get("path", "")
    try:
        os.makedirs(target, exist_ok=True)
        return {"status": "ok"}
    except Exception as e:
        return {"status": "error", "error": str(e)}


# ═════════════════════════════════════════════════════════════
# Outbound WebSocket Agent (Connects to Server for Device ID)
# ═════════════════════════════════════════════════════════════

def get_system_metadata(device_id):
    import getpass, socket, platform
    lan_ips = []
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        lan_ips.append(s.getsockname()[0])
        s.close()
    except Exception:
        pass
    if not lan_ips:
        lan_ips.append("127.0.0.1")

    ssh_running = False
    try:
        test_s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        test_s.settimeout(0.5)
        res = test_s.connect_ex(("127.0.0.1", 22))
        ssh_running = (res == 0)
        test_s.close()
    except Exception:
        pass

    return {
        "type": "agent_info",
        "device_id": device_id,
        "username": getpass.getuser(),
        "hostname": socket.gethostname(),
        "os_name": platform.system(),
        "os_version": platform.release(),
        "platform": sys.platform,
        "lan_ips": lan_ips,
        "primary_ip": lan_ips[0],
        "default_cwd": os.path.expanduser("~"),
        "ssh_running": ssh_running,
        "has_input": HAS_PYNPUT or HAS_XDOTOOL,
    }


# Close code the server uses when the agent token is wrong for this Device ID
AUTH_FAILED_CLOSE_CODE = 4401


async def run_websocket_client(server_url, device_id, token):
    import websockets

    # Format ws:// or wss:// URL
    ws_url = server_url.replace("http://", "ws://").replace("https://", "wss://").rstrip("/")
    target = f"{ws_url}/ws/agent/{device_id}"

    print(f"[*] Connecting to Remote Support Server: {target}")
    reconnect_delay = 1
    unreachable_count = 0

    while True:
        # Input is injected only between take_control and release_control, which the server
        # sends when the host grants or ends control. Each new connection starts in View Only.
        control_active = False
        try:
            async with websockets.connect(target, ping_interval=20, ping_timeout=15) as ws:
                meta = get_system_metadata(device_id)
                # The first message authenticates this agent for the Device ID
                await ws.send(json.dumps({**meta, "token": token}))

                async for message in ws:
                    try:
                        data = json.loads(message)
                        # Unwrap payload if nested inside 'data'
                        if "data" in data and isinstance(data["data"], dict) and "type" in data["data"]:
                            inner = data["data"]
                            if "req_id" in data and "req_id" not in inner:
                                inner["req_id"] = data["req_id"]
                            data = inner

                        mtype = data.get("type")
                        req_id = data.get("req_id")

                        if mtype == "agent_connected":
                            # Sent once the server has accepted the token
                            print("=" * 65)
                            print(f" 🟢 NATIVE AGENT CONNECTED AND ACTIVE FOR DEVICE {device_id}!")
                            print(f" • Remote System: {meta['username']}@{meta['hostname']} ({meta['os_name']})")
                            print(f" • Detected IP: {meta['primary_ip']} | SSH: {'Listening' if meta['ssh_running'] else 'Not detected'}")
                            print(" • Full OS mouse, keyboard, terminal, and file transfer enabled.")
                            print("=" * 65)
                            reconnect_delay = 1
                            unreachable_count = 0
                        elif mtype == "take_control":
                            control_active = True
                            await ws.send(json.dumps({"type": "reply", "reply_to": "take_control", "req_id": req_id, "status": "granted"}))
                            await ws.send(json.dumps({"type": "control_granted"}))
                        elif mtype in ("release_control", "release_all"):
                            control_active = False
                            release_all_inputs()
                            await ws.send(json.dumps({"type": "reply", "reply_to": "release_control", "req_id": req_id, "status": "released"}))
                            await ws.send(json.dumps({"type": "control_released"}))
                        elif mtype in ("mousemove", "mousedown", "mouseup", "click", "dblclick", "contextmenu", "scroll"):
                            if control_active:
                                execute_mouse(data)
                        elif mtype in ("keydown", "keyup"):
                            if control_active:
                                execute_key(data)
                        elif mtype == "clipboard":
                            text = data.get("text", "")
                            if text:
                                execute_clipboard(text)
                        elif mtype == "terminal":
                            result = execute_terminal(data)
                            await ws.send(json.dumps({"type": "reply", "reply_to": "terminal", "req_id": req_id, **result}))
                        elif mtype == "get_home":
                            result = execute_fs_home(data)
                            await ws.send(json.dumps({"type": "reply", "reply_to": "home", "req_id": req_id, **result}))
                        elif mtype == "list":
                            result = execute_fs_list(data)
                            await ws.send(json.dumps({"type": "reply", "reply_to": "listing", "req_id": req_id, **result}))
                        elif mtype == "download":
                            result = execute_fs_read_chunk(data)
                            await ws.send(json.dumps({"type": "reply", "reply_to": "download", "req_id": req_id, **result}))
                        elif mtype == "upload_chunk":
                            result = execute_fs_write_chunk(data)
                            await ws.send(json.dumps({"type": "reply", "reply_to": "upload_chunk", "req_id": req_id, **result}))
                        elif mtype == "delete":
                            result = execute_fs_delete(data)
                            await ws.send(json.dumps({"type": "reply", "reply_to": "delete", "req_id": req_id, **result}))
                        elif mtype == "mkdir":
                            result = execute_fs_mkdir(data)
                            await ws.send(json.dumps({"type": "reply", "reply_to": "mkdir", "req_id": req_id, **result}))
                        elif mtype == "get_info":
                            info = get_system_metadata(device_id)
                            await ws.send(json.dumps({"type": "reply", "reply_to": "info", "req_id": req_id, **info}))
                    except Exception as parse_err:
                        print(f"[Agent Error] {parse_err}")

        except Exception as conn_err:
            close_frame = getattr(conn_err, "rcvd", None)
            if close_frame is not None and close_frame.code == AUTH_FAILED_CLOSE_CODE:
                # Retrying with the same token cannot succeed
                print(f"[!] The server rejected the agent token for {device_id}.")
                print("    Copy the current command from the Host screen and run it again.")
                return
            print(f"[!] Server connection interrupted: {conn_err}. Reconnecting in {reconnect_delay}s...")
            if isinstance(conn_err, OSError):
                unreachable_count += 1
                # Quick-tunnel addresses change when the tunnel restarts, so a saved one can go stale
                if unreachable_count in (1, 10) or unreachable_count % 60 == 0:
                    print(f"[!] Cannot reach the server at {server_url}. If the Host page now shows a different")
                    print("    address, copy the command from the Host page and run it again.")
            reconnect_wait = reconnect_delay
            reconnect_delay = min(reconnect_delay * 2, 20)
        else:
            reconnect_wait = 0
        finally:
            if control_active:
                # Never leave buttons or modifier keys held down when the link drops mid-control
                release_all_inputs()
        await asyncio.sleep(reconnect_wait)


# ═════════════════════════════════════════════════════════════
# Install Once: start automatically at login
# ═════════════════════════════════════════════════════════════

SERVICE_LABEL = "com.remotedesktopsupport.agent"
SYSTEMD_UNIT = "remote-desktop-support-agent.service"
WINDOWS_RUN_VALUE = "RemoteDesktopSupportAgent"
WINDOWS_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
# An installed agent with a rejected token keeps waiting, so re-running --install relinks it
INSTALLED_AUTH_RETRY_SECONDS = 60


def install_dir():
    if sys.platform == "darwin":
        return os.path.expanduser("~/Library/Application Support/RemoteDesktopSupport")
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~\\AppData\\Local")
        return os.path.join(base, "RemoteDesktopSupport")
    base = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
    return os.path.join(base, "remote-desktop-support")


def installed_paths():
    root = install_dir()
    return {
        "dir": root,
        "script": os.path.join(root, "agent.py"),
        "config": os.path.join(root, "config.json"),
        "log": os.path.join(root, "agent.log"),
        "lock": os.path.join(root, "agent.lock"),
        "pid": os.path.join(root, "agent.pid"),
        "plist": os.path.expanduser(f"~/Library/LaunchAgents/{SERVICE_LABEL}.plist"),
        "unit": os.path.join(
            os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config"), "systemd", "user", SYSTEMD_UNIT
        ),
        "autostart": os.path.join(
            os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config"), "autostart",
            "remote-desktop-support-agent.desktop",
        ),
    }


def load_installed_config():
    try:
        with open(installed_paths()["config"], "r", encoding="utf-8") as f:
            config = json.load(f)
        if config.get("server") and config.get("device_id") and config.get("token"):
            return config
    except Exception:
        pass
    return None


def write_private_file(path, content):
    """Write a file only this user can read (it may hold the agent token)."""
    tmp = f"{path}.tmp"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(content)
    os.replace(tmp, path)


def fetch_agent_source(server_url):
    """This script's own source; piped into python3 it has no file, so fetch it from the server."""
    own = globals().get("__file__")
    if own and os.path.isfile(own):
        with open(own, "r", encoding="utf-8") as f:
            return f.read()
    import urllib.request
    with urllib.request.urlopen(f"{server_url.rstrip('/')}/agent.py", timeout=30) as resp:
        source = resp.read().decode("utf-8")
    compile(source, "agent.py", "exec")
    return source


def background_python():
    """Interpreter for the installed agent; on Windows pythonw.exe so no console window opens."""
    exe = sys.executable
    if sys.platform == "win32":
        candidate = os.path.join(os.path.dirname(exe), "pythonw.exe")
        if os.path.exists(candidate):
            return candidate
    return exe


def run_quiet(cmd):
    try:
        return subprocess.run(cmd, check=False, capture_output=True, text=True)
    except Exception as e:
        return subprocess.CompletedProcess(cmd, 1, "", str(e))


class SingleInstance:
    """One companion agent per user account, so input is never injected twice."""

    def __init__(self, path):
        self.path = path
        self.fd = None

    def acquire(self):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        self.fd = os.open(self.path, os.O_RDWR | os.O_CREAT, 0o600)
        try:
            if sys.platform == "win32":
                import msvcrt
                msvcrt.locking(self.fd, msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True
        except OSError:
            os.close(self.fd)
            self.fd = None
            return False

    def release(self):
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None


def stop_running_agent(paths):
    """Stop an agent started without a service manager (Windows Run key or XDG autostart)."""
    probe = SingleInstance(paths["lock"])
    if probe.acquire():
        probe.release()
        return
    try:
        with open(paths["pid"], "r") as f:
            pid = int(f.read().strip())
    except Exception:
        return
    if sys.platform == "win32":
        run_quiet(["taskkill", "/PID", str(pid), "/F"])
    else:
        import signal
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            pass
    import time
    for _ in range(20):
        if probe.acquire():
            probe.release()
            return
        time.sleep(0.25)


def install_macos(paths, python_exe):
    import plistlib
    plist = {
        "Label": SERVICE_LABEL,
        "ProgramArguments": [python_exe, paths["script"], "--run-installed"],
        "RunAtLoad": True,
        "KeepAlive": True,
        "ThrottleInterval": 10,
        "ProcessType": "Interactive",
        # Input injection needs the logged-in GUI session
        "LimitLoadToSessionType": "Aqua",
        # launchd starts services with a bare PATH and no SHELL, which the remote terminal needs
        "EnvironmentVariables": {
            "PYTHONUNBUFFERED": "1",
            "PATH": os.environ.get("PATH") or "/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin",
            "SHELL": os.environ.get("SHELL") or "/bin/zsh",
        },
        "StandardOutPath": paths["log"],
        "StandardErrorPath": paths["log"],
    }
    os.makedirs(os.path.dirname(paths["plist"]), exist_ok=True)
    with open(paths["plist"], "wb") as f:
        plistlib.dump(plist, f)
    domain = f"gui/{os.getuid()}"
    run_quiet(["launchctl", "bootout", f"{domain}/{SERVICE_LABEL}"])
    result = run_quiet(["launchctl", "bootstrap", domain, paths["plist"]])
    if result.returncode != 0:
        result = run_quiet(["launchctl", "load", "-w", paths["plist"]])
    if result.returncode != 0:
        raise RuntimeError(f"launchctl could not start the agent: {(result.stderr or result.stdout).strip()}")
    return f"LaunchAgent {paths['plist']}"


def uninstall_macos(paths):
    run_quiet(["launchctl", "bootout", f"gui/{os.getuid()}/{SERVICE_LABEL}"])
    if os.path.exists(paths["plist"]):
        run_quiet(["launchctl", "unload", "-w", paths["plist"]])
        os.remove(paths["plist"])


def install_linux(paths, python_exe):
    has_systemd = shutil.which("systemctl") and run_quiet(["systemctl", "--user", "show-environment"]).returncode == 0
    if has_systemd:
        unit = "\n".join([
            "[Unit]",
            "Description=Remote Desktop Support companion agent",
            "After=graphical-session.target network-online.target",
            "StartLimitIntervalSec=0",
            "",
            "[Service]",
            f'ExecStart="{python_exe}" "{paths["script"]}" --run-installed',
            "Restart=always",
            "RestartSec=10",
            "Environment=PYTHONUNBUFFERED=1",
            "",
            "[Install]",
            "WantedBy=default.target",
            "",
        ])
        os.makedirs(os.path.dirname(paths["unit"]), exist_ok=True)
        with open(paths["unit"], "w", encoding="utf-8") as f:
            f.write(unit)
        # Lets the agent start now with this session's display; at later logins the desktop imports it
        run_quiet(["systemctl", "--user", "import-environment", "DISPLAY", "XAUTHORITY", "WAYLAND_DISPLAY"])
        run_quiet(["systemctl", "--user", "daemon-reload"])
        result = run_quiet(["systemctl", "--user", "enable", SYSTEMD_UNIT])
        if result.returncode == 0:
            result = run_quiet(["systemctl", "--user", "restart", SYSTEMD_UNIT])
        if result.returncode != 0:
            raise RuntimeError(f"systemctl could not start the agent: {(result.stderr or result.stdout).strip()}")
        return f"systemd user unit {paths['unit']}"

    # No systemd user session: start with the desktop through XDG autostart
    entry = "\n".join([
        "[Desktop Entry]",
        "Type=Application",
        "Name=Remote Desktop Support Agent",
        f'Exec="{python_exe}" "{paths["script"]}" --run-installed',
        "NoDisplay=true",
        "X-GNOME-Autostart-enabled=true",
        "",
    ])
    os.makedirs(os.path.dirname(paths["autostart"]), exist_ok=True)
    with open(paths["autostart"], "w", encoding="utf-8") as f:
        f.write(entry)
    stop_running_agent(paths)
    start_detached(paths, python_exe)
    return f"autostart entry {paths['autostart']}"


def uninstall_linux(paths):
    if shutil.which("systemctl"):
        run_quiet(["systemctl", "--user", "disable", "--now", SYSTEMD_UNIT])
    for key in ("unit", "autostart"):
        if os.path.exists(paths[key]):
            os.remove(paths[key])
    if shutil.which("systemctl"):
        run_quiet(["systemctl", "--user", "daemon-reload"])
    stop_running_agent(paths)


def windows_command_line(python_exe, script):
    return subprocess.list2cmdline([python_exe, script, "--run-installed"])


def install_windows(paths, python_exe):
    # The per-user Run key needs no administrator rights and starts in the interactive session
    import winreg
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, WINDOWS_RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
        winreg.SetValueEx(key, WINDOWS_RUN_VALUE, 0, winreg.REG_SZ, windows_command_line(python_exe, paths["script"]))
    stop_running_agent(paths)
    start_detached(paths, python_exe)
    return f"login entry HKCU\\{WINDOWS_RUN_KEY}\\{WINDOWS_RUN_VALUE}"


def uninstall_windows(paths):
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, WINDOWS_RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            winreg.DeleteValue(key, WINDOWS_RUN_VALUE)
    except OSError:
        pass
    stop_running_agent(paths)


def start_detached(paths, python_exe):
    kwargs = {"stdin": subprocess.DEVNULL, "stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL, "close_fds": True}
    if sys.platform == "win32":
        kwargs["creationflags"] = 0x00000008 | 0x00000200  # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True
    subprocess.Popen([python_exe, paths["script"], "--run-installed"], **kwargs)


def install_agent(server_url, device_id, token):
    paths = installed_paths()
    try:
        import websockets  # noqa: F401
    except ImportError:
        print("[!] The 'websockets' package could not be installed for this Python:")
        print(f"    {sys.executable} -m pip install --user websockets pynput")
        sys.exit(1)

    os.makedirs(paths["dir"], exist_ok=True)
    try:
        source = fetch_agent_source(server_url)
    except Exception as e:
        print(f"[!] Could not download the agent from {server_url}: {e}")
        sys.exit(1)
    with open(paths["script"], "w", encoding="utf-8") as f:
        f.write(source)
    write_private_file(paths["config"], json.dumps(
        {"server": server_url.rstrip("/"), "device_id": device_id, "token": token}, indent=2
    ))

    python_exe = background_python()
    try:
        if sys.platform == "darwin":
            where = install_macos(paths, python_exe)
        elif sys.platform == "win32":
            where = install_windows(paths, python_exe)
        else:
            where = install_linux(paths, python_exe)
    except Exception as e:
        print(f"[!] Installed the files but could not register the login service: {e}")
        sys.exit(1)

    print("=" * 65)
    print(f" ✅ Companion agent installed for {device_id}")
    print(f" • Starts automatically at login ({where})")
    print(f" • Files and log: {paths['dir']}")
    if sys.platform == "darwin":
        print(" • macOS asks to allow Accessibility for Python. Allow it in System Settings >")
        print("   Privacy & Security > Accessibility so remote mouse and keyboard work:")
        print(f"   {os.path.realpath(python_exe)}")
    print(" • To remove it: python3 \"%s\" --uninstall" % paths["script"])
    print("=" * 65)


def uninstall_agent():
    paths = installed_paths()
    if sys.platform == "darwin":
        uninstall_macos(paths)
    elif sys.platform == "win32":
        uninstall_windows(paths)
    else:
        uninstall_linux(paths)
    names = ["config", "script", "pid", "log"]
    probe = SingleInstance(paths["lock"])
    if probe.acquire():
        # A manually started agent still holds it otherwise; deleting it would allow a second agent
        probe.release()
        names.append("lock")
    for key in names:
        try:
            os.remove(paths[key])
        except OSError:
            pass
    try:
        os.rmdir(paths["dir"])
    except OSError:
        pass
    print("[*] Companion agent uninstalled; it no longer starts at login.")


def request_macos_accessibility():
    """Ask macOS to list this Python under Accessibility; without it injected input is dropped."""
    try:
        import ctypes, ctypes.util
        ax = ctypes.cdll.LoadLibrary(ctypes.util.find_library("ApplicationServices"))
        cf = ctypes.cdll.LoadLibrary(ctypes.util.find_library("CoreFoundation"))
        ax.AXIsProcessTrusted.restype = ctypes.c_bool
        if ax.AXIsProcessTrusted():
            return True
        cf.CFStringCreateWithCString.restype = ctypes.c_void_p
        cf.CFStringCreateWithCString.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_uint32]
        cf.CFDictionaryCreate.restype = ctypes.c_void_p
        cf.CFDictionaryCreate.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_long,
                                          ctypes.c_void_p, ctypes.c_void_p]
        ax.AXIsProcessTrustedWithOptions.restype = ctypes.c_bool
        ax.AXIsProcessTrustedWithOptions.argtypes = [ctypes.c_void_p]
        key = cf.CFStringCreateWithCString(None, b"AXTrustedCheckOptionPrompt", 0x08000100)
        true_value = ctypes.c_void_p.in_dll(cf, "kCFBooleanTrue")
        keys = (ctypes.c_void_p * 1)(key)
        values = (ctypes.c_void_p * 1)(true_value.value)
        options = cf.CFDictionaryCreate(
            None, keys, values, 1,
            ctypes.addressof(ctypes.c_char.in_dll(cf, "kCFTypeDictionaryKeyCallBacks")),
            ctypes.addressof(ctypes.c_char.in_dll(cf, "kCFTypeDictionaryValueCallBacks")),
        )
        return bool(ax.AXIsProcessTrustedWithOptions(options))
    except Exception:
        return None


def wait_for_linux_display():
    """systemd may start the unit before the desktop exports DISPLAY; pick it up, then restart."""
    if os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY") or not shutil.which("systemctl"):
        return
    import time
    for _ in range(24):
        env = run_quiet(["systemctl", "--user", "show-environment"]).stdout or ""
        found = {}
        for line in env.splitlines():
            name, _, value = line.partition("=")
            if name in ("DISPLAY", "XAUTHORITY", "WAYLAND_DISPLAY") and value:
                found[name] = value
        if found.get("DISPLAY") or found.get("WAYLAND_DISPLAY"):
            os.environ.update(found)
            # Input drivers bind to the display at import time
            os.execv(sys.executable, [sys.executable, *sys.argv])
        time.sleep(5)
    print("[!] No graphical session found; remote mouse and keyboard stay off until the next login.")


def run_installed():
    paths = installed_paths()
    if sys.stdout is None or sys.platform == "win32":
        # pythonw.exe has no console, so keep a log next to the config
        try:
            if os.path.exists(paths["log"]) and os.path.getsize(paths["log"]) > 1024 * 1024:
                os.remove(paths["log"])
            log = open(paths["log"], "a", buffering=1, encoding="utf-8")
            sys.stdout = sys.stderr = log
        except Exception:
            pass
    if sys.platform.startswith("linux"):
        wait_for_linux_display()
    if sys.platform == "darwin" and request_macos_accessibility() is False:
        print("[!] Accessibility is not allowed for this Python, so remote mouse and keyboard are ignored.")
        print(f"    Allow it in System Settings > Privacy & Security > Accessibility: {os.path.realpath(sys.executable)}")
    while True:
        config = load_installed_config()
        if not config:
            print(f"[!] No agent configuration at {paths['config']}; run --install again.")
            return 1
        try:
            asyncio.run(run_websocket_client(config["server"], config["device_id"], config["token"]))
        except KeyboardInterrupt:
            return 0
        except Exception as e:
            print(f"[Agent Error] {e}")
        # Returning means the token was rejected; wait for a reinstall instead of exiting,
        # which the service manager would only restart.
        import time
        time.sleep(INSTALLED_AUTH_RETRY_SECONDS)


# ═════════════════════════════════════════════════════════════
# Main Entry Point
# ═════════════════════════════════════════════════════════════

def prompt_value(label):
    """Ask on the terminal when one is attached (not when the script is piped into python3)."""
    if not sys.stdin.isatty():
        return ""
    try:
        return input(f"\nEnter the {label} shown on the Host screen: ").strip()
    except (KeyboardInterrupt, EOFError):
        print("\nExiting.")
        sys.exit(0)


def get_device_id(custom_id=None):
    if custom_id:
        return custom_id.strip()
    env_id = os.environ.get("DEVICE_ID")
    if env_id:
        return env_id.strip()

    id_file = os.path.expanduser("~/.remote_desktop_device_id")
    if os.path.exists(id_file):
        try:
            with open(id_file, "r") as f:
                saved = f.read().strip()
                if saved:
                    return saved
        except Exception:
            pass

    return prompt_value("Device ID (e.g. AG-XXX-XXX-XXX)")


def get_agent_token(custom_token=None):
    if custom_token:
        return custom_token.strip()
    env_token = os.environ.get("AGENT_TOKEN")
    if env_token:
        return env_token.strip()
    return prompt_value("agent token")


def main():
    parser = argparse.ArgumentParser(description="Remote Desktop Support Native Host Companion Agent")
    parser.add_argument("--device", "-d", help="Your Device ID (e.g. AG-816-555-726) shown on screen")
    parser.add_argument("--token", "-t", help="Agent token shown on the Host screen (or set AGENT_TOKEN)")
    parser.add_argument("--server", "-s", default=DEFAULT_SERVER, help="Signaling Server URL")
    parser.add_argument("--install", action="store_true",
                        help="Install for this user and start automatically at every login")
    parser.add_argument("--uninstall", action="store_true", help="Remove the installed agent and its login entry")
    parser.add_argument("--run-installed", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()

    if args.uninstall:
        uninstall_agent()
        return

    lock = SingleInstance(installed_paths()["lock"])
    if args.run_installed:
        # A manually started agent may hold the lock; take over once it exits
        import time
        while not lock.acquire():
            time.sleep(10)
        write_private_file(installed_paths()["pid"], str(os.getpid()))
        sys.exit(run_installed())

    device_id = get_device_id(args.device)
    token = get_agent_token(args.token)
    if not device_id or not token:
        print("[!] A Device ID and agent token are required. Copy the full command from the Host screen:")
        print("    curl -sSL <server>/agent.py | python3 - --device AG-XXX-XXX-XXX --token <agent token>")
        sys.exit(2)

    # Normalize Device ID
    device_id = device_id.replace(" ", "-").upper()
    if not device_id.startswith("AG-"):
        device_id = f"AG-{device_id}"

    if args.install:
        install_agent(args.server, device_id, token)
        return

    if not lock.acquire():
        installed = load_installed_config()
        print("[!] A companion agent is already running for this user account.")
        if installed and installed["device_id"] == device_id:
            print(f"    The installed agent already serves {device_id}.")
        elif installed:
            print(f"    It is installed for {installed['device_id']}. To link it to {device_id} instead, run")
            print("    the install command from the Host screen.")
        sys.exit(1)
    write_private_file(installed_paths()["pid"], str(os.getpid()))

    try:
        asyncio.run(run_websocket_client(args.server, device_id, token))
    except KeyboardInterrupt:
        print("\nStopping Native Companion Agent...")

if __name__ == "__main__":
    main()
