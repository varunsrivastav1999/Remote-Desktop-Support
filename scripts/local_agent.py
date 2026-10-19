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
        elif btn_idx == 2:
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
            shell_bin = os.environ.get("SHELL", "/bin/sh")
            proc = subprocess.run(
                [shell_bin, "-c", cmd],
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
