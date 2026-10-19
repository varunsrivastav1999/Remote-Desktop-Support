#!/usr/bin/env python3
"""
Remote Desktop Support — Native Host Companion Agent
Provides native OS mouse, keyboard, and terminal control when the host is accessed via Web Browser (Chrome/Firefox/Edge).
Listens on http://127.0.0.1:8765.
"""

import sys
import os
import json
import subprocess
from http.server import HTTPServer, BaseHTTPRequestHandler

PORT = 8765

# Detect screen resolution
SCREEN_WIDTH = 1920
SCREEN_HEIGHT = 1080

try:
    from AppKit import NSScreen
    frame = NSScreen.mainScreen().frame()
    SCREEN_WIDTH = int(frame.size.width)
    SCREEN_HEIGHT = int(frame.size.height)
except Exception:
    try:
        import tkinter
        root = tkinter.Tk()
        root.withdraw()
        SCREEN_WIDTH = int(root.winfo_screenwidth())
        SCREEN_HEIGHT = int(root.winfo_screenheight())
    except Exception:
        pass

# Initialize mouse and keyboard controllers via pynput
HAS_PYNPUT = False
mouse = None
keyboard = None

try:
    from pynput.mouse import Controller as MouseController, Button
    from pynput.keyboard import Controller as KeyboardController, Key
    mouse = MouseController()
    keyboard = KeyboardController()
    HAS_PYNPUT = True
except Exception as e:
    print(f"[Companion Agent Warning] pynput not loaded: {e}")

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

import base64
import shutil

class CompanionHandler(BaseHTTPRequestHandler):
    def _send_cors(self, status=200, content_type="application/json"):
        self.send_response(status)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Content-Type", content_type)
        self.end_headers()

    def do_OPTIONS(self):
        self._send_cors(204)

    def do_GET(self):
        if self.path == "/health":
            self._send_cors(200)
            payload = {
                "status": "ok",
                "has_native_input": HAS_PYNPUT,
                "screen_width": SCREEN_WIDTH,
                "screen_height": SCREEN_HEIGHT,
                "platform": sys.platform,
            }
            self.wfile.write(json.dumps(payload).encode("utf-8"))
        elif self.path == "/fs/home":
            self.handle_fs_home({})
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

        if self.path == "/mouse":
            self.handle_mouse(data)
        elif self.path == "/key":
            self.handle_key(data)
        elif self.path == "/terminal":
            self.handle_terminal(data)
        elif self.path == "/fs/home":
            self.handle_fs_home(data)
        elif self.path == "/fs/list":
            self.handle_fs_list(data)
        elif self.path == "/fs/read_chunk":
            self.handle_fs_read_chunk(data)
        elif self.path == "/fs/write_chunk":
            self.handle_fs_write_chunk(data)
        elif self.path == "/fs/delete":
            self.handle_fs_delete(data)
        elif self.path == "/fs/mkdir":
            self.handle_fs_mkdir(data)
        else:
            self._send_cors(404)
            self.wfile.write(b'{"error": "not found"}')

    def handle_mouse(self, data):
        mtype = data.get("type", "mousemove")
        x_norm = float(data.get("x", 0))
        y_norm = float(data.get("y", 0))
        btn_idx = int(data.get("button", 0))

        btn = Button.left
        if btn_idx == 1:
            btn = Button.middle
        elif btn_idx == 2 or mtype == "contextmenu":
            btn = Button.right

        target_x = max(0, min(SCREEN_WIDTH - 1, int(x_norm * SCREEN_WIDTH)))
        target_y = max(0, min(SCREEN_HEIGHT - 1, int(y_norm * SCREEN_HEIGHT)))

        if HAS_PYNPUT and mouse:
            try:
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
            except Exception as e:
                print(f"[Companion Agent Mouse Error] {e}")

        self._send_cors(200)
        self.wfile.write(b'{"status": "ok"}')

    def handle_key(self, data):
        ktype = data.get("type", "keydown")
        key_str = data.get("key", "")

        if HAS_PYNPUT and keyboard and key_str:
            try:
                target_key = KEY_MAP.get(key_str, key_str if len(key_str) == 1 else None)
                if target_key:
                    if ktype == "keydown":
                        keyboard.press(target_key)
                    elif ktype == "keyup":
                        keyboard.release(target_key)
            except Exception as e:
                print(f"[Companion Agent Key Error] {e}")

        self._send_cors(200)
        self.wfile.write(b'{"status": "ok"}')

    def handle_terminal(self, data):
        cmd = data.get("command", "").strip()
        cwd = data.get("cwd") or os.path.expanduser("~")

        if not cmd:
            self._send_cors(200)
            self.wfile.write(json.dumps({"stdout": "", "stderr": "", "exit_code": 0}).encode("utf-8"))
            return

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
            res = {
                "stdout": proc.stdout,
                "stderr": proc.stderr,
                "exit_code": proc.returncode,
            }
        except subprocess.TimeoutExpired:
            res = {"stdout": "", "stderr": "Command timed out after 15 seconds\n", "exit_code": 124}
        except Exception as e:
            res = {"stdout": "", "stderr": f"Execution error: {e}\n", "exit_code": 1}

        self._send_cors(200)
        self.wfile.write(json.dumps(res).encode("utf-8"))

    # ═════════════════════════════════════════════════════════════
    # Filesystem Operations
    # ═════════════════════════════════════════════════════════════

    def handle_fs_home(self, _data):
        home = os.path.expanduser("~")
        payload = {
            "path": home,
            "separator": os.sep,
            "platform": sys.platform,
        }
        self._send_cors(200)
        self.wfile.write(json.dumps(payload).encode("utf-8"))

    def handle_fs_list(self, data):
        dir_path = data.get("path") or os.path.expanduser("~")
        entries = []
        try:
            if os.path.exists(dir_path) and os.path.isdir(dir_path):
                with os.scandir(dir_path) as it:
                    for entry in it:
                        try:
                            is_dir = entry.is_dir(follow_symlinks=False)
                            size = 0 if is_dir else entry.stat().st_size
                            entries.append({
                                "name": entry.name,
                                "path": entry.path,
                                "is_dir": is_dir,
                                "size": size,
                            })
                        except (PermissionError, OSError):
                            continue
            # Sort: directories first, then alphabetically
            entries.sort(key=lambda x: (not x["is_dir"], x["name"].lower()))
            res = {"path": dir_path, "entries": entries, "error": None}
        except Exception as e:
            res = {"path": dir_path, "entries": [], "error": str(e)}

        self._send_cors(200)
        self.wfile.write(json.dumps(res).encode("utf-8"))

    def handle_fs_read_chunk(self, data):
        path = data.get("path", "")
        offset = int(data.get("offset", 0))
        chunk_size = int(data.get("size", 49152))

        try:
            total_size = os.path.getsize(path)
            with open(path, "rb") as f:
                f.seek(offset)
                chunk_data = f.read(chunk_size)
            
            encoded = base64.b64encode(chunk_data).decode("ascii")
            res = {
                "name": os.path.basename(path),
                "data": encoded,
                "size": len(chunk_data),
                "offset": offset,
                "total_size": total_size,
                "eof": (offset + len(chunk_data)) >= total_size,
            }
        except Exception as e:
            res = {"error": str(e), "eof": True, "size": 0, "data": ""}

        self._send_cors(200)
        self.wfile.write(json.dumps(res).encode("utf-8"))

    def handle_fs_write_chunk(self, data):
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
            
            res = {"status": "ok", "path": target_path, "written": len(raw_bytes)}
        except Exception as e:
            res = {"error": str(e), "status": "error"}

        self._send_cors(200)
        self.wfile.write(json.dumps(res).encode("utf-8"))

    def handle_fs_delete(self, data):
        target = data.get("path", "")
        try:
            if os.path.isdir(target):
                shutil.rmtree(target)
            elif os.path.isfile(target):
                os.remove(target)
            res = {"status": "ok"}
        except Exception as e:
            res = {"status": "error", "error": str(e)}

        self._send_cors(200)
        self.wfile.write(json.dumps(res).encode("utf-8"))

    def handle_fs_mkdir(self, data):
        target = data.get("path", "")
        try:
            os.makedirs(target, exist_ok=True)
            res = {"status": "ok"}
        except Exception as e:
            res = {"status": "error", "error": str(e)}

        self._send_cors(200)
        self.wfile.write(json.dumps(res).encode("utf-8"))

    def log_message(self, format, *args):
        # Silence routine request logging
        return

def run_agent():
    server = HTTPServer(("127.0.0.1", PORT), CompanionHandler)
    print("=" * 60)
    print(" Remote Desktop Support: Native Companion Agent")
    print(f" • Listening locally on http://127.0.0.1:{PORT}")
    print(f" • Native input injection (pynput): {'ENABLED' if HAS_PYNPUT else 'DISABLED'}")
    print(f" • Detected Screen Resolution: {SCREEN_WIDTH} x {SCREEN_HEIGHT}")
    print(" • Ready to handle remote mouse, keyboard & terminal requests")
    print("=" * 60)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping Native Companion Agent...")
        server.server_close()

if __name__ == "__main__":
    run_agent()
