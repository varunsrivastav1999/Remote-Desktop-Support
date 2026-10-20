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

    while True:
        # Input is injected only between take_control and release_control, which the server
        # sends when the host grants or ends control. Each new connection starts in View Only.
        control_active = False
        try:
            async with websockets.connect(target, ping_interval=20, ping_timeout=15) as ws:
                meta = get_system_metadata(device_id)
                # The first message authenticates this agent for the Device ID
                await ws.send(json.dumps({**meta, "token": token}))

                print("=" * 65)
                print(f" 🟢 NATIVE AGENT CONNECTED AND ACTIVE FOR DEVICE {device_id}!")
                print(f" • Remote System: {meta['username']}@{meta['hostname']} ({meta['os_name']})")
                print(f" • Detected IP: {meta['primary_ip']} | SSH: {'Listening' if meta['ssh_running'] else 'Not detected'}")
                print(" • Full OS mouse, keyboard, terminal, and file transfer enabled.")
                print("=" * 65)
                reconnect_delay = 1

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

                        if mtype == "take_control":
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
    args = parser.parse_args()

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

    try:
        asyncio.run(run_websocket_client(args.server, device_id, token))
    except KeyboardInterrupt:
        print("\nStopping Native Companion Agent...")

if __name__ == "__main__":
    main()
