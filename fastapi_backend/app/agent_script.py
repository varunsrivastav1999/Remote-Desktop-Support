#!/usr/bin/env python3
"""
Remote Desktop Support — Native Host Companion Agent
Provides native OS mouse, keyboard, terminal, and filesystem control across Linux, macOS, and Windows.
Supports:
  1. Direct Outbound WebSocket connection to Signaling Server (/ws/agent/{device_id})
  2. Local HTTP Server on http://127.0.0.1:8765 with Private Network Access CORS
  3. Native input injection via pynput, Quartz (macOS), Win32 (Windows), and xdotool (Linux)
"""

import sys
import os
import json
import base64
import shutil
import argparse
import asyncio
import threading
import subprocess
from http.server import HTTPServer, BaseHTTPRequestHandler

PORT = 8765
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
        "Control": Key.ctrl,
        "Alt": Key.alt,
        "Meta": Key.cmd,
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
                steps_y = -1 if delta_y > 0 else (1 if delta_y < 0 else 0)
                steps_x = -1 if delta_x > 0 else (1 if delta_x < 0 else 0)
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
            x_key = key_str.lower()
            if key_str == "Enter": x_key = "Return"
            elif key_str == "Escape": x_key = "Escape"
            elif key_str == "Backspace": x_key = "BackSpace"
            elif key_str == "Control": x_key = "Control_L"
            elif key_str == "Shift": x_key = "Shift_L"
            elif key_str == "Alt": x_key = "Alt_L"
            elif key_str == "ArrowUp": x_key = "Up"
            elif key_str == "ArrowDown": x_key = "Down"
            elif key_str == "ArrowLeft": x_key = "Left"
            elif key_str == "ArrowRight": x_key = "Right"
            if ktype == "keydown":
                run_xdotool("keydown", x_key)
            elif ktype == "keyup":
                run_xdotool("keyup", x_key)
            return {"status": "ok"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    return {"status": "error", "message": "No key driver available"}


def execute_terminal(data):
    cmd = data.get("command", "").strip()
    cwd = data.get("cwd") or os.path.expanduser("~")
    if not cmd:
        return {"stdout": "", "stderr": "", "exit_code": 0}

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
            cwd=cwd,
        )
        return {
            "stdout": proc.stdout,
            "stderr": proc.stderr,
            "exit_code": proc.returncode,
        }
    except subprocess.TimeoutExpired:
        return {"stdout": "", "stderr": "Command timed out after 15 seconds\n", "exit_code": 124}
    except Exception as e:
        return {"stdout": "", "stderr": f"Execution error: {e}\n", "exit_code": 1}


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
# Local HTTP Server (Handles Local Mixed-Content / LAN)
# ═════════════════════════════════════════════════════════════

class CompanionHandler(BaseHTTPRequestHandler):
    def _send_cors(self, status=200, content_type="application/json"):
        self.send_response(status)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Access-Control-Allow-Private-Network", "true")
        self.send_header("Content-Type", content_type)
        self.end_headers()

    def do_OPTIONS(self):
        self._send_cors(204)

    def do_GET(self):
        if self.path == "/health":
            self._send_cors(200)
            payload = {
                "status": "ok",
                "has_native_input": HAS_PYNPUT or HAS_XDOTOOL,
                "screen_width": SCREEN_WIDTH,
                "screen_height": SCREEN_HEIGHT,
                "platform": sys.platform,
            }
            self.wfile.write(json.dumps(payload).encode("utf-8"))
        elif self.path == "/fs/home":
            res = execute_fs_home()
            self._send_cors(200)
            self.wfile.write(json.dumps(res).encode("utf-8"))
        else:
            self._send_cors(404)
            self.wfile.write(b'{"error": "not found"}')

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode("utf-8") if content_length > 0 else "{}"
        try:
            data = json.loads(body)
        except Exception:
            data = {}

        path = self.path.rstrip("/")
        if path == "/mouse":
            res = execute_mouse(data)
        elif path == "/key":
            res = execute_key(data)
        elif path == "/terminal":
            res = execute_terminal(data)
        elif path == "/fs/home":
            res = execute_fs_home(data)
        elif path == "/fs/list":
            res = execute_fs_list(data)
        elif path == "/fs/read_chunk":
            res = execute_fs_read_chunk(data)
        elif path == "/fs/write_chunk":
            res = execute_fs_write_chunk(data)
        elif path == "/fs/delete":
            res = execute_fs_delete(data)
        elif path == "/fs/mkdir":
            res = execute_fs_mkdir(data)
        else:
            self._send_cors(404)
            self.wfile.write(b'{"error": "not found"}')
            return

        self._send_cors(200)
        self.wfile.write(json.dumps(res).encode("utf-8"))

    def log_message(self, format, *args):
        return

def start_http_server():
    try:
        server = HTTPServer(("127.0.0.1", PORT), CompanionHandler)
        server.serve_forever()
    except Exception as e:
        print(f"[Companion HTTP Warning] Could not bind 127.0.0.1:{PORT}: {e}")


# ═════════════════════════════════════════════════════════════
# Outbound WebSocket Agent (Connects to Server for Device ID)
# ═════════════════════════════════════════════════════════════

async def run_websocket_client(server_url, device_id):
    import websockets

    # Format ws:// or wss:// URL
    ws_url = server_url.replace("http://", "ws://").replace("https://", "wss://").rstrip("/")
    target = f"{ws_url}/ws/agent/{device_id}"

    print(f"[*] Connecting to Remote Support Server: {target}")
    reconnect_delay = 1

    while True:
        try:
            async with websockets.connect(target, ping_interval=20, ping_timeout=15) as ws:
                print("=" * 65)
                print(f" 🟢 NATIVE AGENT CONNECTED AND ACTIVE FOR DEVICE {device_id}!")
                print(" • Full OS mouse, keyboard, and terminal control enabled.")
                print(" • Screen interactions from controller will execute directly.")
                print("=" * 65)
                reconnect_delay = 1

                async for message in ws:
                    try:
                        data = json.loads(message)
                        mtype = data.get("type")

                        if mtype in ("mousemove", "mousedown", "mouseup", "click", "dblclick", "contextmenu", "scroll"):
                            execute_mouse(data)
                        elif mtype in ("keydown", "keyup"):
                            execute_key(data)
                        elif mtype == "terminal":
                            result = execute_terminal(data)
                            await ws.send(json.dumps({"type": "reply", "reply_to": "terminal", **result}))
                        elif mtype == "get_home":
                            result = execute_fs_home(data)
                            await ws.send(json.dumps({"type": "reply", "reply_to": "home", **result}))
                        elif mtype == "list":
                            result = execute_fs_list(data)
                            await ws.send(json.dumps({"type": "reply", "reply_to": "listing", **result}))
                        elif mtype == "download":
                            result = execute_fs_read_chunk(data)
                            await ws.send(json.dumps({"type": "reply", "reply_to": "download", **result}))
                        elif mtype == "upload_chunk":
                            result = execute_fs_write_chunk(data)
                            await ws.send(json.dumps({"type": "reply", "reply_to": "upload_chunk", **result}))
                        elif mtype == "delete":
                            result = execute_fs_delete(data)
                            await ws.send(json.dumps({"type": "reply", "reply_to": "delete", **result}))
                        elif mtype == "mkdir":
                            result = execute_fs_mkdir(data)
                            await ws.send(json.dumps({"type": "reply", "reply_to": "mkdir", **result}))
                    except Exception as parse_err:
                        print(f"[Agent Error] {parse_err}")

        except Exception as conn_err:
            print(f"[!] Server connection interrupted: {conn_err}. Reconnecting in {reconnect_delay}s...")
            await asyncio.sleep(reconnect_delay)
            reconnect_delay = min(reconnect_delay * 2, 20)


# ═════════════════════════════════════════════════════════════
# Main Entry Point
# ═════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="Remote Desktop Support Native Host Companion Agent")
    parser.add_argument("--device", "-d", help="Your Device ID (e.g. AG-816-555-726) shown on screen")
    parser.add_argument("--server", "-s", default=DEFAULT_SERVER, help="Signaling Server URL")
    args = parser.parse_args()

    # Always start local HTTP server in background thread
    t = threading.Thread(target=start_http_server, daemon=True)
    t.start()

    device_id = args.device
    if not device_id:
        print("=" * 65)
        print(" Remote Desktop Support — Native Host Companion Agent")
        print(f" • Detected Screen: {SCREEN_WIDTH} x {SCREEN_HEIGHT}")
        print(f" • Input Support: {'pynput' if HAS_PYNPUT else ('xdotool' if HAS_XDOTOOL else 'None')}")
        print(f" • Local HTTP listener: http://127.0.0.1:{PORT}")
        print("=" * 65)
        try:
            device_id = input("\nEnter your Device ID shown on the Host screen (e.g. AG-XXX-XXX-XXX): ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nExiting.")
            sys.exit(0)

    if device_id:
        # Normalize Device ID
        device_id = device_id.replace(" ", "-").upper()
        if not device_id.startswith("AG-"):
            device_id = f"AG-{device_id}"

        try:
            asyncio.run(run_websocket_client(args.server, device_id))
        except KeyboardInterrupt:
            print("\nStopping Native Companion Agent...")
    else:
        print("[*] No Device ID supplied. Running in standalone local HTTP mode on 127.0.0.1:8765...")
        try:
            t.join()
        except KeyboardInterrupt:
            print("\nStopping Native Companion Agent...")

if __name__ == "__main__":
    main()
