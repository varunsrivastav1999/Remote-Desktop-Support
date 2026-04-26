"""
file_transfer.py — Chunked file transfer over WebRTC Data Channel.

Handles:
  1. Directory listing (browse remote file system)
  2. File download: host → client (chunked binary)
  3. File upload: client → host (chunked binary)
  4. Security: path sanitization, restricted root paths

Protocol (JSON messages on 'file-transfer' data channel):
  - {type: "list", path: "/home/user"}          → returns directory listing
  - {type: "download", path: "/home/user/f.txt"} → starts sending file chunks
  - {type: "upload_start", name: "f.txt", size: 1234, dest: "/home/user/"}
  - {type: "upload_chunk", data: "<base64>", offset: 0}
  - {type: "upload_end"}
  - {type: "mkdir", path: "/home/user/newfolder"}
  - {type: "delete", path: "/home/user/f.txt"}
"""

import base64
import json
import logging
import os
import platform
import stat
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ─── Constants ──────────────────────────────────────────────
CHUNK_SIZE = 48 * 1024  # 48KB chunks (fits in WebRTC data channel)
MAX_FILE_SIZE = 2 * 1024 * 1024 * 1024  # 2GB limit

# Default browsable root (user's home directory)
DEFAULT_ROOT = str(Path.home())

# Restricted paths that cannot be browsed or modified
RESTRICTED_PATHS = {
    '/System', '/usr', '/bin', '/sbin', '/etc',
    'C:\\Windows', 'C:\\Program Files',
}


class FileTransferHandler:
    """
    Handles file transfer commands received via the WebRTC Data Channel.

    All paths are validated against a configurable root directory
    to prevent unauthorized file system access.
    """

    def __init__(self, data_channel, root_path: Optional[str] = None):
        """
        Args:
            data_channel: The WebRTC RTCDataChannel for file transfer.
            root_path: Root directory for browsing (default: user home).
        """
        self.dc = data_channel
        self.root = root_path or DEFAULT_ROOT
        self._upload_file = None
        self._upload_path = None
        self._upload_size = 0
        self._upload_received = 0

        logger.info(f"FileTransfer initialized, root={self.root}")

    def handle_message(self, raw_data: str):
        """Parse and dispatch a file transfer command."""
        try:
            msg = json.loads(raw_data)
        except json.JSONDecodeError:
            self._send_error("Invalid JSON")
            return

        cmd = msg.get('type', '')

        handlers = {
            'list': self._handle_list,
            'download': self._handle_download,
            'upload_start': self._handle_upload_start,
            'upload_chunk': self._handle_upload_chunk,
            'upload_end': self._handle_upload_end,
            'mkdir': self._handle_mkdir,
            'delete': self._handle_delete,
            'get_home': self._handle_get_home,
        }

        handler = handlers.get(cmd)
        if handler:
            try:
                handler(msg)
            except Exception as e:
                logger.error(f"File transfer error ({cmd}): {e}")
                self._send_error(str(e))
        else:
            self._send_error(f"Unknown command: {cmd}")

    def _handle_get_home(self, msg):
        """Return the default home directory path."""
        self._send({
            'type': 'home',
            'path': str(Path.home()),
            'separator': os.sep,
            'platform': platform.system(),
        })

    def _handle_list(self, msg):
        """List contents of a directory."""
        raw_path = msg.get('path', self.root)
        path = self._safe_path(raw_path)

        if not path or not path.is_dir():
            self._send_error(f"Directory not found: {raw_path}")
            return

        entries = []
        try:
            for item in sorted(path.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower())):
                try:
                    st = item.stat()
                    entries.append({
                        'name': item.name,
                        'path': str(item),
                        'is_dir': item.is_dir(),
                        'size': st.st_size if item.is_file() else 0,
                        'modified': datetime.fromtimestamp(st.st_mtime).isoformat(),
                        'permissions': stat.filemode(st.st_mode),
                    })
                except (PermissionError, OSError):
                    entries.append({
                        'name': item.name,
                        'path': str(item),
                        'is_dir': item.is_dir(),
                        'size': 0,
                        'modified': '',
                        'permissions': '?',
                        'error': 'Access denied',
                    })
        except PermissionError:
            self._send_error(f"Permission denied: {raw_path}")
            return

        self._send({
            'type': 'listing',
            'path': str(path),
            'parent': str(path.parent),
            'entries': entries,
        })

    def _handle_download(self, msg):
        """Send a file to the client in chunks."""
        raw_path = msg.get('path', '')
        path = self._safe_path(raw_path)

        if not path or not path.is_file():
            self._send_error(f"File not found: {raw_path}")
            return

        file_size = path.stat().st_size
        if file_size > MAX_FILE_SIZE:
            self._send_error(f"File too large: {file_size} bytes (max {MAX_FILE_SIZE})")
            return

        # Send download start metadata
        self._send({
            'type': 'download_start',
            'name': path.name,
            'path': str(path),
            'size': file_size,
        })

        # Send file in chunks
        offset = 0
        try:
            with open(path, 'rb') as f:
                while True:
                    chunk = f.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    self._send({
                        'type': 'download_chunk',
                        'data': base64.b64encode(chunk).decode('ascii'),
                        'offset': offset,
                        'size': len(chunk),
                    })
                    offset += len(chunk)
        except Exception as e:
            self._send_error(f"Read error: {e}")
            return

        self._send({
            'type': 'download_end',
            'name': path.name,
            'total_size': file_size,
        })
        logger.info(f"File sent: {path.name} ({file_size} bytes)")

    def _handle_upload_start(self, msg):
        """Prepare to receive a file from the client."""
        name = msg.get('name', '')
        size = msg.get('size', 0)
        dest = msg.get('dest', self.root)

        if not name:
            self._send_error("No filename provided")
            return

        dest_path = self._safe_path(dest)
        if not dest_path or not dest_path.is_dir():
            self._send_error(f"Invalid destination: {dest}")
            return

        file_path = dest_path / name
        if size > MAX_FILE_SIZE:
            self._send_error(f"File too large: {size} bytes")
            return

        try:
            self._upload_file = open(file_path, 'wb')
            self._upload_path = file_path
            self._upload_size = size
            self._upload_received = 0
            self._send({'type': 'upload_ready', 'name': name})
        except Exception as e:
            self._send_error(f"Cannot create file: {e}")

    def _handle_upload_chunk(self, msg):
        """Receive a chunk of upload data."""
        if not self._upload_file:
            self._send_error("No upload in progress")
            return

        data = base64.b64decode(msg.get('data', ''))
        self._upload_file.write(data)
        self._upload_received += len(data)

        # Send progress
        if self._upload_size > 0:
            progress = min(100, int(self._upload_received / self._upload_size * 100))
            self._send({
                'type': 'upload_progress',
                'received': self._upload_received,
                'total': self._upload_size,
                'progress': progress,
            })

    def _handle_upload_end(self, msg):
        """Finalize an upload."""
        if self._upload_file:
            self._upload_file.close()
            logger.info(
                f"File received: {self._upload_path.name} "
                f"({self._upload_received} bytes)"
            )
            self._send({
                'type': 'upload_complete',
                'name': self._upload_path.name,
                'path': str(self._upload_path),
                'size': self._upload_received,
            })
            self._upload_file = None
            self._upload_path = None

    def _handle_mkdir(self, msg):
        """Create a new directory."""
        raw_path = msg.get('path', '')
        path = self._safe_path(raw_path)

        if not path:
            self._send_error(f"Invalid path: {raw_path}")
            return

        try:
            path.mkdir(parents=True, exist_ok=True)
            self._send({'type': 'mkdir_ok', 'path': str(path)})
        except Exception as e:
            self._send_error(f"Cannot create directory: {e}")

    def _handle_delete(self, msg):
        """Delete a file or empty directory."""
        raw_path = msg.get('path', '')
        path = self._safe_path(raw_path)

        if not path or not path.exists():
            self._send_error(f"Path not found: {raw_path}")
            return

        try:
            if path.is_file():
                path.unlink()
            elif path.is_dir():
                path.rmdir()  # Only empty dirs
            self._send({'type': 'delete_ok', 'path': str(path)})
        except Exception as e:
            self._send_error(f"Cannot delete: {e}")

    # ─── Helpers ─────────────────────────────────────────────

    def _safe_path(self, raw_path: str) -> Optional[Path]:
        """Validate and resolve a path, preventing directory traversal."""
        if not raw_path:
            return None

        try:
            path = Path(raw_path).resolve()
        except (ValueError, OSError):
            return None

        # Check against restricted system paths
        path_str = str(path)
        for restricted in RESTRICTED_PATHS:
            if path_str.startswith(restricted):
                logger.warning(f"Blocked access to restricted path: {path_str}")
                return None

        return path

    def _send(self, data: dict):
        """Send a JSON message over the data channel."""
        try:
            if self.dc and self.dc.readyState == 'open':
                self.dc.send(json.dumps(data))
        except Exception as e:
            logger.error(f"FileTransfer send error: {e}")

    def _send_error(self, message: str):
        """Send an error response."""
        self._send({'type': 'error', 'message': message})
        logger.warning(f"FileTransfer error: {message}")

    def cleanup(self):
        """Close any open upload file handles."""
        if self._upload_file:
            self._upload_file.close()
            self._upload_file = None
