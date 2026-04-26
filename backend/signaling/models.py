"""
Models for the signaling app.

Stores remote support session metadata — each session is identified
by a unique 9-digit code that the host shares with the support tech.
"""

import random
import string

from django.db import models
from django.utils import timezone


def generate_session_code():
    """Generate a unique 9-digit session code formatted as XXX-XXX-XXX."""
    digits = ''.join(random.choices(string.digits, k=9))
    return f"{digits[:3]}-{digits[3:6]}-{digits[6:9]}"


class Session(models.Model):
    """
    Represents a remote support session.

    The host agent creates a session and receives a code.
    The support tech joins by entering that code in the Vue client.
    """

    class Status(models.TextChoices):
        WAITING = 'waiting', 'Waiting for peer'
        CONNECTED = 'connected', 'Connected'
        DISCONNECTED = 'disconnected', 'Disconnected'
        EXPIRED = 'expired', 'Expired'

    code = models.CharField(
        max_length=11,
        unique=True,
        default=generate_session_code,
        help_text='Unique session code (format: XXX-XXX-XXX)',
    )
    status = models.CharField(
        max_length=15,
        choices=Status.choices,
        default=Status.WAITING,
    )
    host_identifier = models.CharField(
        max_length=255,
        blank=True,
        default='',
        help_text='Hostname or IP of the host machine',
    )
    alias = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text='Custom display name for the session',
    )
    created_at = models.DateTimeField(default=timezone.now)
    connected_at = models.DateTimeField(null=True, blank=True)
    disconnected_at = models.DateTimeField(null=True, blank=True)
    
    # Internal tracking for signaling
    host_channel = models.CharField(max_length=255, blank=True, default='')
    client_channel = models.CharField(max_length=255, blank=True, default='')

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['code']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return f"Session {self.code} ({self.status})"

    @property
    def is_active(self):
        return self.status in (self.Status.WAITING, self.Status.CONNECTED)
