import asyncio
import logging
import os
import platform
import subprocess
import threading
from typing import Optional

logger = logging.getLogger(__name__)

class TerminalHandler:
    """
    Spawns a local shell and bridges stdin/stdout to a WebRTC data channel.
    Uses pty on POSIX systems for full terminal emulation (colors, interactive apps),
    and standard subprocess pipes on Windows.
    """
    def __init__(self, data_channel, loop=None):
        self.data_channel = data_channel
        self.loop = loop or asyncio.get_event_loop()
        self.shell_process = None
        self.fd = None
        self._running = False
        self._read_thread = None
        
        # Start shell on init
        self.start_shell()

    def start_shell(self):
        if self._running:
            return

        is_posix = platform.system() != 'Windows'
        
        try:
            if is_posix:
                import pty
                # Spawn shell with pseudo-terminal
                shell = os.environ.get("SHELL", "bash" if os.path.exists("/bin/bash") else "sh")
                master_fd, slave_fd = pty.openpty()
                
                self.shell_process = subprocess.Popen(
                    [shell],
                    stdin=slave_fd,
                    stdout=slave_fd,
                    stderr=slave_fd,
                    close_fds=True,
                    preexec_fn=os.setsid
                )
                os.close(slave_fd)
                self.fd = master_fd
                self._running = True
                
                # Start a thread to read from PTY (asyncio loop shouldn't block on os.read)
                self._read_thread = threading.Thread(target=self._posix_read_loop, daemon=True)
                self._read_thread.start()
            else:
                # Windows fallback without winpty
                shell = os.environ.get("COMSPEC", "cmd.exe")
                self.shell_process = subprocess.Popen(
                    [shell],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    bufsize=0
                )
                self._running = True
                self._read_thread = threading.Thread(target=self._windows_read_loop, daemon=True)
                self._read_thread.start()
                
            logger.info(f"Terminal started: {shell}")
        except Exception as e:
            logger.error(f"Failed to start terminal: {e}")

    def _posix_read_loop(self):
        while self._running and self.shell_process.poll() is None:
            try:
                data = os.read(self.fd, 4096)
                if not data:
                    break
                self._send_to_channel(data.decode('utf-8', errors='replace'))
            except OSError:
                break
            except Exception as e:
                logger.error(f"PTY read error: {e}")
                break
        self.cleanup()

    def _windows_read_loop(self):
        while self._running and self.shell_process.poll() is None:
            try:
                data = self.shell_process.stdout.read(4096)
                if not data:
                    break
                self._send_to_channel(data.decode('utf-8', errors='replace'))
            except Exception as e:
                logger.error(f"Subprocess read error: {e}")
                break
        self.cleanup()

    def _send_to_channel(self, text: str):
        try:
            if self.data_channel and self.data_channel.readyState == "open":
                self.loop.call_soon_threadsafe(self.data_channel.send, text)
        except Exception as e:
            logger.debug(f"Error sending terminal output: {e}")

    def handle_message(self, msg):
        """Receive input from WebRTC and write to shell stdin."""
        if not self._running or not self.shell_process:
            return
            
        try:
            if isinstance(msg, bytes):
                data = msg
            else:
                data = msg.encode('utf-8')
                
            if self.fd is not None:
                # POSIX PTY
                os.write(self.fd, data)
            else:
                # Windows PIPEs
                self.shell_process.stdin.write(data)
                self.shell_process.stdin.flush()
        except Exception as e:
            logger.error(f"Error writing to terminal: {e}")

    def cleanup(self):
        self._running = False
        try:
            if self.shell_process:
                self.shell_process.terminate()
        except:
            pass
        try:
            if self.fd is not None:
                os.close(self.fd)
        except:
            pass
        self.shell_process = None
        self.fd = None
        logger.info("Terminal cleaned up")
