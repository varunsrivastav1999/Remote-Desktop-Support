"""
WebSocket consumer for WebRTC signaling.

This is the core of the signaling server. It handles:
  1. Peer registration (host agent and Vue client join a session room)
  2. SDP offer/answer relay between peers
  3. ICE candidate relay between peers
  4. Session lifecycle management (connect, disconnect, cleanup)

The consumer does NOT process or relay any media — it only
brokers the WebRTC handshake so peers can establish a direct
P2P connection.
"""

import json
import logging

from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async

from .models import Session

logger = logging.getLogger(__name__)


class SignalingConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer that relays WebRTC signaling messages
    between the host agent and the Vue.js client within a session.
    """

    async def connect(self):
        """Accept the WebSocket connection and join the session group."""
        self.session_code = self.scope['url_route']['kwargs']['session_code']
        self.room_group_name = f'session_{self.session_code}'
        self.peer_role = None  # Will be set to 'host' or 'client'

        # Verify session exists and is joinable
        session = await self.get_session()
        if session is None:
            logger.warning(f"Rejected connection: session {self.session_code} not found")
            await self.close()
            return

        # Join the Channels group for this session
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name,
        )

        await self.accept()
        logger.info(f"Peer connected to session {self.session_code} ({self.channel_name})")

    async def disconnect(self, close_code):
        """Leave the session group and update session status."""
        # Notify other peers that this peer disconnected
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'peer_disconnected',
                'role': self.peer_role or 'unknown',
                'sender_channel': self.channel_name,
            }
        )

        # Leave the group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name,
        )

        # Update session status and clear channel
        if self.peer_role:
            await self.update_session_status(Session.Status.DISCONNECTED, clear_channel=True)

        logger.info(
            f"Peer ({self.peer_role or 'unknown'}) disconnected from "
            f"session {self.session_code} (code={close_code})"
        )

    async def receive(self, text_data):
        """
        Handle incoming WebSocket messages.

        Expected message types:
          - register: Peer identifies as 'host' or 'client'
          - offer: SDP offer from client → host
          - answer: SDP answer from host → client
          - ice: ICE candidate from either peer
        """
        try:
            data = json.loads(text_data)
        except json.JSONDecodeError:
            await self.send_error('Invalid JSON')
            return

        msg_type = data.get('type')

        if msg_type == 'register':
            await self.handle_register(data)
        elif msg_type == 'ping':
            await self.send_json({'type': 'pong'})
        elif msg_type == 'ice_restart_request':
            # Relay restart request to the OTHER peer
            await self.handle_signaling(data)
        elif msg_type in ('offer', 'answer', 'ice'):
            await self.handle_signaling(data)
        else:
            await self.send_error(f'Unknown message type: {msg_type}')

    # ─── Message Handlers ────────────────────────────────────

    async def handle_register(self, data):
        """Register this peer as either 'host' or 'client'."""
        role = data.get('role')
        if role not in ('host', 'client'):
            await self.send_error("Role must be 'host' or 'client'")
            return

        self.peer_role = role
        logger.info(f"Peer registered as '{role}' in session {self.session_code}")

        # Notify the room that a peer has registered
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'peer_registered',
                'role': role,
                'sender_channel': self.channel_name,
            }
        )

        # Update session and check for existing peer
        peer_info = await self.register_peer_in_db(role, self.channel_name)
        
        # If the OTHER peer is already there, tell the current peer immediately
        other_role = 'client' if role == 'host' else 'host'
        if peer_info.get(f'{other_role}_exists'):
            await self.send_json({
                'type': 'peer_joined',
                'role': other_role,
            })

        # If a client just joined, update session status
        if role == 'client':
            await self.update_session_status(Session.Status.CONNECTED)

    async def handle_signaling(self, data):
        """Relay SDP offers/answers and ICE candidates to other peers."""
        # Broadcast to the group, excluding the sender
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'signaling_message',
                'message': data,
                'sender_channel': self.channel_name,
            }
        )

    # ─── Group Event Handlers ────────────────────────────────
    # These are called by the channel layer when a message is
    # sent to the group. The method name matches the 'type' field.

    async def signaling_message(self, event):
        """Relay a signaling message to this peer (if not the sender)."""
        if event['sender_channel'] != self.channel_name:
            await self.send(text_data=json.dumps(event['message']))

    async def peer_registered(self, event):
        """Notify this peer that another peer has registered."""
        if event['sender_channel'] != self.channel_name:
            await self.send(text_data=json.dumps({
                'type': 'peer_joined',
                'role': event['role'],
            }))

    async def peer_disconnected(self, event):
        """Notify this peer that another peer has disconnected."""
        if event['sender_channel'] != self.channel_name:
            await self.send(text_data=json.dumps({
                'type': 'peer_left',
                'role': event['role'],
            }))

    # ─── Helpers ─────────────────────────────────────────────

    async def send_error(self, message):
        """Send an error message back to the client."""
        await self.send(text_data=json.dumps({
            'type': 'error',
            'message': message,
        }))

    @database_sync_to_async
    def get_session(self):
        """Fetch the session from the database."""
        try:
            return Session.objects.get(code=self.session_code)
        except Session.DoesNotExist:
            return None

    @database_sync_to_async
    def register_peer_in_db(self, role, channel_name):
        """Save the peer's channel name and check if the other peer exists."""
        try:
            session = Session.objects.get(code=self.session_code)
            if role == 'host':
                session.host_channel = channel_name
            else:
                session.client_channel = channel_name
            session.save()
            
            return {
                'host_exists': bool(session.host_channel),
                'client_exists': bool(session.client_channel),
            }
        except Session.DoesNotExist:
            return {}

    @database_sync_to_async
    def update_session_status(self, new_status, clear_channel=False):
        """Update the session's status and optionally clear the channel name."""
        from django.utils import timezone
        try:
            session = Session.objects.get(code=self.session_code)
            session.status = new_status
            
            if clear_channel and self.peer_role:
                if self.peer_role == 'host':
                    session.host_channel = ''
                else:
                    session.client_channel = ''
            
            if new_status == Session.Status.CONNECTED:
                session.connected_at = timezone.now()
            elif new_status == Session.Status.DISCONNECTED:
                session.disconnected_at = timezone.now()
            session.save()
        except Session.DoesNotExist:
            pass
