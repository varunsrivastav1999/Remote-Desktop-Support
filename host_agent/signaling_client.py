"""
signaling_client.py — WebSocket client for connecting to the Django signaling server.

Handles:
  1. Creating a session via REST API → receives session code
  2. Connecting to the WebSocket signaling channel
  3. WebRTC peer connection setup (SDP offer, ICE candidates)
  4. Adding the screen capture track
  5. Setting up the data channel for remote input
"""

import asyncio
import json
import logging
from typing import Optional, Callable

import aiohttp
from aiortc import RTCPeerConnection, RTCSessionDescription, RTCIceCandidate
from aiortc.contrib.media import MediaRelay

from screen_capture import ScreenCaptureTrack
from input_handler import InputHandler

logger = logging.getLogger(__name__)

# Public STUN servers for NAT traversal
ICE_SERVERS = [
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
    ):
        """
        Args:
            server_url: Base URL of the signaling server (e.g., "http://localhost:8000")
            fps: Target screen capture FPS
            monitor: Monitor index to capture
        """
        self.server_url = server_url.rstrip('/')
        self.fps = fps
        self.monitor = monitor

        self.session_code: Optional[str] = None
        self.ws: Optional[aiohttp.ClientWebSocketResponse] = None
        self.pc: Optional[RTCPeerConnection] = None
        self.screen_track: Optional[ScreenCaptureTrack] = None
        self.input_handler: Optional[InputHandler] = None
        self._ice_candidate_queue = []
        self._running = False

    async def create_session(self, host_identifier: str = "") -> str:
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
                if response.status != 201:
                    text = await response.text()
                    raise RuntimeError(f"Failed to create session: {response.status} — {text}")
                
                data = await response.json()
                self.session_code = data['code']
                logger.info(f"Session created: {self.session_code}")
                return self.session_code

    async def connect_and_serve(self):
        """
        Connect to the signaling WebSocket and serve the remote desktop.
        Main loop with auto-reconnect logic.
        """
        if not self.session_code:
            raise RuntimeError("No session code. Call create_session() first.")

        # Determine WebSocket URL
        ws_scheme = "wss" if self.server_url.startswith("https") else "ws"
        http_scheme_len = len("https://" if "https" in self.server_url else "http://")
        host = self.server_url[http_scheme_len:]
        ws_url = f"{ws_scheme}://{host}/ws/signaling/{self.session_code}/"

        self._running = True
        reconnect_delay = 1

        while self._running:
            logger.info(f"Connecting to signaling server: {ws_url}...")
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.ws_connect(ws_url, heartbeat=25) as ws:
                        self.ws = ws
                        reconnect_delay = 1 # Reset on success

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
                candidate = RTCIceCandidate(
                    sdpMid=candidate_data.get('sdpMid', ''),
                    sdpMLineIndex=candidate_data.get('sdpMLineIndex', 0),
                    candidate=candidate_data.get('candidate', ''),
                )
                if self.pc and self.pc.remoteDescription:
                    await self.pc.addIceCandidate(candidate)
                else:
                    self._ice_candidate_queue.append(candidate)

    async def _create_offer(self, ice_restart=False):
        """Set up the WebRTC peer connection and create an SDP offer."""
        logger.info(f"Setting up WebRTC peer connection (restart={ice_restart})...")

        if self.pc and not ice_restart:
            await self.pc.close()
        
        config = {"iceServers": ICE_SERVERS}
        
        # If restarting, we reuse the tracks if possible or just fresh start
        if not self.pc:
            self.pc = RTCPeerConnection(configuration=config)
            
            # Screen capture track
            self.screen_track = ScreenCaptureTrack(fps=self.fps, monitor=self.monitor)
            self.pc.addTrack(self.screen_track)
            
            # Input handler
            self.input_handler = InputHandler(self.screen_track.screen_size)
            
            # Data channel
            self.data_channel = self.pc.createDataChannel("control", ordered=True)
            @self.data_channel.on("open")
            def on_open(): logger.info("Data channel OPEN")
            @self.data_channel.on("message")
            def on_message(msg): self.input_handler.handle_event(msg)

            @self.pc.on("icecandidate")
            def on_ice_candidate(candidate):
                if candidate:
                    asyncio.ensure_future(self._send({
                        "type": "ice",
                        "candidate": {
                            "candidate": candidate.candidate,
                            "sdpMid": candidate.sdpMid,
                            "sdpMLineIndex": candidate.sdpMLineIndex,
                        }
                    }))

            @self.pc.on("connectionstatechange")
            async def on_state_change():
                logger.info(f"Connection state: {self.pc.connectionState}")
                if self.pc.connectionState == "failed":
                    logger.warning("Connection failed, waiting for restart...")

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

    async def _send(self, data: dict):
        if self.ws and not self.ws.closed:
            await self.ws.send_json(data)

    async def _cleanup(self):
        self._running = False
        if self.screen_track:
            self.screen_track.stop()
            self.screen_track = None
        if self.pc:
            await self.pc.close()
            self.pc = None
        logger.info("Resources cleaned up")

