"""
WebSocket URL routing for the signaling app.
"""

from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(
        r'ws/signaling/(?P<session_code>[\d\-]+)/$',
        consumers.SignalingConsumer.as_asgi(),
    ),
]
