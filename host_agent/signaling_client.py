"""
signaling_client.py — WebSocket client for connecting to the Django signaling server.

Handles:
  1. Creating a session via REST API → receives session code
  2. Connecting to the WebSocket signaling channel
  3. WebRTC peer connection setup (SDP offer, ICE candidates)
  4. Adding the screen capture track
  5. Setting up data channels for remote input, file transfer, and chat
  6. Clipboard synchronization
  7. Quality preset switching
  8. Multi-monitor management
"""

import asyncio
import json
import logging
import platform
from typing import Optional
from urllib.parse import urlparse, urlunparse

import aiohttp
from aiortc import (
    RTCConfiguration,
    RTCIceServer,
    RTCPeerConnection,
    RTCSessionDescription,
)
from aiortc.contrib.media import MediaRelay
from aiortc.sdp import candidate_from_sdp, candidate_to_sdp

from screen_capture import ScreenCaptureTrack
from input_handler import InputHandler
from file_transfer import FileTransferHandler

logger = logging.getLogger(__name__)

# Public STUN servers for NAT traversal
DEFAULT_ICE_SERVERS = [
    {"urls": "stun:stun.l.google.com:19302"},
    {"urls": "stun:stun1.l.google.com:19302"},
    {"urls": "stun:stun2.l.google.com:19302"},
    {"urls": "stun:stun3.l.google.com:19302"},
    {"urls": "stun:stun4.l.google.com:19302"},
    {"urls": "stun:stun.ekiga.net"},
    {"urls": "stun:stun.ideasip.com"},
    {"urls": "stun:stun.rixtelecom.se"},
    {"urls": "stun:stun.schlund.de"},
    {"urls": "stun:stun.voiparound.com"},
    {"urls": "stun:stun.voipbuster.com"},
    {"urls": "stun:stun.voipstunt.com"},
    {"urls": "stun:stun.voxgratia.org"},
]


class SignalingClient:
    """
    Connects the host agent to the Django signaling server
    and manages the WebRTC peer connection lifecycle.
    """

    def __init__(
        self,
        server_url: str,
        fps: int = 30,
        monitor: int = 1,
        quality: str = 'medium',
        password: str = '',
        extra_ice_servers: Optional[list[dict]] = None,
    ):
        """
        Args:
            server_url: Base URL of the signaling server (e.g., "http://localhost:8000")
            fps: Target screen capture FPS
            monitor: Monitor index to capture
            quality: Initial quality preset ('ultra-low', 'low', 'medium', 'high', 'ultra')
            password: Optional password for secure unattended access
        """
        self.server_url = self._normalize_server_url(server_url)
        self.fps = fps
        self.monitor = monitor
        self.quality = quality
        self.password = password
        self.is_authenticated = not bool(password)
        self.ice_servers = [*DEFAULT_ICE_SERVERS, *(extra_ice_servers or [])]

        self.session_code: Optional[str] = None
        self.ws: Optional[aiohttp.ClientWebSocketResponse] = None
        self.pc: Optional[RTCPeerConnection] = None
        self.screen_track: Optional[ScreenCaptureTrack] = None
        self.input_handler: Optional[InputHandler] = None
        self.file_handler: Optional[FileTransferHandler] = None
        self._ice_candidate_queue = []
        self._running = False

        # Clipboard state
        self._last_clipboard = ''
        self._clipboard_task = None

    async def create_session(self, host_identifier: str = "", alias: str = "") -> str:
        """
        Create a new session via the REST API.

        Returns:
            The session code (e.g., "123-456-789")
        """
        url = f"{self.server_url}/api/session/create/"
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                json={"host_identifier": host_identifier},
            ) as response:
                if response.status not in (200, 201):
                    text = await response.text()
                    raise RuntimeError(f"Failed to create session: {response.status} — {text}")

                data = await response.json()
                self.session_code = data['code']
                logger.info(f"Session created: {self.session_code}")
                
            # If an alias is provided, call the rename API
            if alias and self.session_code:
                rename_url = f"{self.server_url}/api/session/{self.session_code}/rename/"
                try:
                    async with session.patch(rename_url, json={"alias": alias}) as rename_response:
                        if rename_response.status == 200:
                            logger.info(f"Session alias set to: {alias}")
                        else:
                            logger.warning(f"Failed to set alias: {rename_response.status}")
                except Exception as e:
                    logger.warning(f"Error setting alias: {e}")
                    
            return self.session_code

    async def connect_and_serve(self):
        """
        Connect to the signaling WebSocket and serve the remote desktop.
        Main loop with auto-reconnect logic.
        """
        if not self.session_code:
            raise RuntimeError("No session code. Call create_session() first.")

        ws_url = self._build_ws_url()

        self._running = True
        reconnect_delay = 1

        while self._running:
            logger.info(f"Connecting to signaling server: {ws_url}...")
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.ws_connect(ws_url, heartbeat=25) as ws:
                        self.ws = ws
                        reconnect_delay = 1  # Reset on success

                        # Register as host
                        await self._send({"type": "register", "role": "host"})
                        logger.info("Registered as host, waiting for client...")

                        # Message loop
                        async for msg in ws:
                            if msg.type == aiohttp.WSMsgType.TEXT:
                                await self._handle_message(json.loads(msg.data))
                            elif msg.type == aiohttp.WSMsgType.CLOSED:
                                logger.info("WebSocket closed by server")
                                break
                            elif msg.type == aiohttp.WSMsgType.ERROR:
                                logger.error(f"WebSocket error: {ws.exception()}")
                                break

                if not self._running:
                    break

                logger.info(f"Reconnecting in {reconnect_delay}s...")
                await asyncio.sleep(reconnect_delay)
                reconnect_delay = min(reconnect_delay * 2, 60)

            except Exception as e:
                logger.error(f"Connection failed: {e}")
                if not self._running:
                    break
                logger.info(f"Retrying in {reconnect_delay}s...")
                await asyncio.sleep(reconnect_delay)
                reconnect_delay = min(reconnect_delay * 2, 60)

        await self._cleanup()

    async def _handle_message(self, data: dict):
        """Route incoming signaling messages."""
        msg_type = data.get('type')

        if msg_type == 'peer_joined':
            logger.info(f"Peer joined as '{data.get('role')}'")
            if data.get('role') == 'client':
                # Client joined — create offer (or restart)
                await self._create_offer()

        elif msg_type == 'ice_restart_request':
            logger.info("Received ICE restart request")
            await self._create_offer(ice_restart=True)

        elif msg_type == 'peer_left':
            logger.info(f"Peer left ({data.get('role')})")
            # Stop clipboard sync
            self._stop_clipboard_sync()
            # Don't cleanup everything, just wait for new peer
            if self.pc:
                await self.pc.close()
                self.pc = None

        elif msg_type == 'answer':
            logger.info("Received SDP answer")
            sdp = data.get('sdp', {})
            if self.pc:
                await self.pc.setRemoteDescription(
                    RTCSessionDescription(sdp=sdp.get('sdp', sdp), type=sdp.get('type', 'answer'))
                )
                for candidate in self._ice_candidate_queue:
                    await self.pc.addIceCandidate(candidate)
                self._ice_candidate_queue = []

        elif msg_type == 'ice':
            candidate_data = data.get('candidate', {})
            if candidate_data and candidate_data.get('candidate'):
                candidate = self._candidate_from_browser(candidate_data)
                if self.pc and self.pc.remoteDescription:
                    await self.pc.addIceCandidate(candidate)
                else:
                    self._ice_candidate_queue.append(candidate)
            elif self.pc and self.pc.remoteDescription:
                await self.pc.addIceCandidate(None)

    async def _create_offer(self, ice_restart=False):
        """Set up the WebRTC peer connection and create an SDP offer."""
        logger.info(f"Setting up WebRTC peer connection (restart={ice_restart})...")

        if self.pc and not ice_restart:
            await self.pc.close()

        config = RTCConfiguration(
            iceServers=[self._ice_server_from_dict(server) for server in self.ice_servers]
        )

        # If restarting, we reuse the tracks if possible or just fresh start
        if not self.pc:
            self.pc = RTCPeerConnection(configuration=config)

            # Screen capture track with quality preset
            self.screen_track = ScreenCaptureTrack(
                fps=self.fps,
                monitor=self.monitor,
                quality=self.quality,
                requires_auth=bool(self.password),
            )
            self.pc.addTrack(self.screen_track)

            # Input handler
            self.input_handler = InputHandler(self.screen_track.screen_size)

            # ─── Control Data Channel ────────────────────────
            self.data_channel = self.pc.createDataChannel("control", ordered=True)

            @self.data_channel.on("open")
            def on_control_open():
                logger.info("Control data channel OPEN")
                if not self.is_authenticated:
                    self._send_dc({"type": "auth_required"})
                else:
                    self._on_authenticated()

            @self.data_channel.on("message")
            def on_control_message(msg):
                self._handle_control_message(msg)

            # ─── File Transfer Data Channel ──────────────────
            self.file_channel = self.pc.createDataChannel("file-transfer", ordered=True)

            @self.file_channel.on("open")
            def on_file_open():
                logger.info("File transfer data channel OPEN")
                self.file_handler = FileTransferHandler(self.file_channel)

            @self.file_channel.on("message")
            def on_file_message(msg):
                if self.file_handler:
                    self.file_handler.handle_message(msg)

            @self.pc.on("icecandidate")
            def on_ice_candidate(candidate):
                if candidate:
                    asyncio.ensure_future(self._send({
                        "type": "ice",
                        "candidate": self._candidate_to_browser(candidate)
                    }))

            @self.pc.on("connectionstatechange")
            async def on_state_change():
                logger.info(f"Connection state: {self.pc.connectionState}")
                if self.pc.connectionState == "failed":
                    logger.warning("Connection failed, waiting for restart...")
                elif self.pc.connectionState == "disconnected":
                    self._stop_clipboard_sync()

        # Create and send offer
        offer = await self.pc.createOffer()
        await self.pc.setLocalDescription(offer)

        await self._send({
            "type": "offer",
            "sdp": {
                "type": self.pc.localDescription.type,
                "sdp": self.pc.localDescription.sdp,
            }
        })
        logger.info("SDP offer sent")

    def _on_authenticated(self):
        """Called when data channel opens or client successfully authenticates."""
        logger.info("Client authenticated. Starting data streams.")
        asyncio.ensure_future(self._send_system_info())
        self._start_clipboard_sync()

    def _handle_control_message(self, raw_data: str):
        """Handle messages on the control data channel."""
        try:
            data = json.loads(raw_data)
        except json.JSONDecodeError:
            # Not JSON — pass to input handler as-is
            if self.is_authenticated and self.input_handler:
                self.input_handler.handle_event(raw_data)
            return

        msg_type = data.get('type', '')

        # ─── Authentication ─────────────────────────────────
        if msg_type == 'auth':
            client_pw = data.get('password', '')
            if client_pw == self.password:
                self.is_authenticated = True
                if self.screen_track:
                    self.screen_track.is_authenticated = True
                self._send_dc({'type': 'auth_result', 'status': 'success'})
                self._on_authenticated()
            else:
                logger.warning("Failed authentication attempt")
                self._send_dc({'type': 'auth_result', 'status': 'failed'})
            return

        if not self.is_authenticated:
            return

        # ─── Quality control ────────────────────────────────
        if msg_type == 'quality':
            preset = data.get('preset', 'medium')
            if self.screen_track:
                self.screen_track.set_quality(preset)
                self._send_dc({'type': 'quality_changed', 'preset': preset})

        # ─── Monitor switching ──────────────────────────────
        elif msg_type == 'switch_monitor':
            index = data.get('index', 1)
            if self.screen_track and self.screen_track.switch_monitor(index):
                # Update input handler with new screen size
                self.input_handler = InputHandler(self.screen_track.screen_size)
                self._send_dc({
                    'type': 'monitor_switched',
                    'index': index,
                    'width': self.screen_track.screen_size[0],
                    'height': self.screen_track.screen_size[1],
                })

        # ─── Clipboard from client ──────────────────────────
        elif msg_type == 'clipboard':
            text = data.get('text', '')
            if text:
                try:
                    import pyperclip
                    pyperclip.copy(text)
                    logger.debug(f"Clipboard set from client ({len(text)} chars)")
                    self._last_clipboard = text
                except Exception as e:
                    logger.warning(f"Failed to set clipboard: {e}")

        # ─── Chat message ───────────────────────────────────
        elif msg_type == 'chat':
            text = data.get('text', '')
            sender = data.get('sender', 'Client')
            timestamp = data.get('timestamp', '')
            logger.info(f"💬 Chat from {sender}: {text}")
            # Echo back confirmation so client knows it was received
            self._send_dc({
                'type': 'chat',
                'text': text,
                'sender': 'host',
                'timestamp': timestamp,
                'delivered': True,
            })

        # ─── Get monitors list ──────────────────────────────
        elif msg_type == 'get_monitors':
            monitors = ScreenCaptureTrack.get_monitors()
            self._send_dc({
                'type': 'monitors',
                'list': monitors,
                'current': self.screen_track.monitor_index if self.screen_track else 1,
            })

        # ─── Get stats ──────────────────────────────────────
        elif msg_type == 'get_stats':
            if self.screen_track:
                self._send_dc({
                    'type': 'host_stats',
                    **self.screen_track.stats,
                })

        # ─── Regular input events (mouse, keyboard, scroll) ─
        else:
            if self.input_handler:
                self.input_handler.handle_event(raw_data)

    async def _send_system_info(self):
        """Send host system information to the client on connect."""
        import socket
        monitors = ScreenCaptureTrack.get_monitors()
        info = {
            'type': 'system_info',
            'hostname': socket.gethostname(),
            'platform': platform.system(),
            'platform_version': platform.version(),
            'machine': platform.machine(),
            'monitors': monitors,
            'current_monitor': self.screen_track.monitor_index if self.screen_track else 1,
            'quality': self.quality,
        }
        self._send_dc(info)

    # ─── Clipboard Sync ──────────────────────────────────────

    def _start_clipboard_sync(self):
        """Start polling the host clipboard for changes."""
        try:
            import pyperclip
            self._clipboard_task = asyncio.ensure_future(self._clipboard_loop())
            logger.info("Clipboard sync started")
        except ImportError:
            logger.warning("pyperclip not installed — clipboard sync disabled")

    def _stop_clipboard_sync(self):
        """Stop clipboard polling."""
        if self._clipboard_task:
            self._clipboard_task.cancel()
            self._clipboard_task = None

    async def _clipboard_loop(self):
        """Poll clipboard every 500ms and send changes to client."""
        import pyperclip
        while True:
            try:
                await asyncio.sleep(0.5)
                current = pyperclip.paste()
                if current and current != self._last_clipboard:
                    self._last_clipboard = current
                    self._send_dc({
                        'type': 'clipboard',
                        'text': current[:50000],  # Limit to 50KB
                    })
            except asyncio.CancelledError:
                break
            except Exception:
                await asyncio.sleep(2)  # Back off on errors

    # ─── Helpers ─────────────────────────────────────────────

    def _send_dc(self, data: dict):
        """Send JSON via the control data channel."""
        try:
            if hasattr(self, 'data_channel') and self.data_channel and self.data_channel.readyState == 'open':
                self.data_channel.send(json.dumps(data))
        except Exception as e:
            logger.debug(f"Data channel send error: {e}")

    async def _send(self, data: dict):
        if self.ws and not self.ws.closed:
            await self.ws.send_json(data)

    def _normalize_server_url(self, server_url: str) -> str:
        server_url = server_url.strip()
        if not server_url.startswith(("http://", "https://")):
            server_url = f"http://{server_url}"
        return server_url.rstrip("/")

    def _build_ws_url(self) -> str:
        parsed = urlparse(self.server_url)
        scheme = "wss" if parsed.scheme == "https" else "ws"
        path = f"/ws/signaling/{self.session_code}/"
        return urlunparse((scheme, parsed.netloc, path, "", "", ""))

    def _candidate_from_browser(self, candidate_data: dict):
        candidate_sdp = candidate_data.get("candidate", "")
        if candidate_sdp.startswith("candidate:"):
            candidate_sdp = candidate_sdp.split(":", 1)[1]

        candidate = candidate_from_sdp(candidate_sdp)
        candidate.sdpMid = candidate_data.get("sdpMid")
        candidate.sdpMLineIndex = candidate_data.get("sdpMLineIndex")
        return candidate

    def _candidate_to_browser(self, candidate) -> dict:
        return {
            "candidate": f"candidate:{candidate_to_sdp(candidate)}",
            "sdpMid": candidate.sdpMid,
            "sdpMLineIndex": candidate.sdpMLineIndex,
        }

    def _ice_server_from_dict(self, server: dict) -> RTCIceServer:
        return RTCIceServer(
            urls=server["urls"],
            username=server.get("username"),
            credential=server.get("credential"),
        )

    async def _cleanup(self):
        self._running = False
        self._stop_clipboard_sync()
        if self.file_handler:
            self.file_handler.cleanup()
            self.file_handler = None
        if self.screen_track:
            self.screen_track.stop()
            self.screen_track = None
        if self.pc:
            await self.pc.close()
            self.pc = None
        logger.info("Resources cleaned up")
