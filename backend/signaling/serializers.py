"""
Serializers for session management REST API.
"""

from rest_framework import serializers
from .models import Session


class SessionCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating a new session (host agent)."""

    class Meta:
        model = Session
        fields = ['id', 'code', 'status', 'host_identifier', 'created_at']
        read_only_fields = ['id', 'created_at']


class SessionJoinSerializer(serializers.Serializer):
    """Serializer for joining an existing session (support tech)."""

    code = serializers.CharField(
        max_length=255,
        help_text='Session code, IP address, or alias to join',
    )

    def validate_code(self, value):
        """Ensure the session exists by code, alias, or host_identifier."""
        identifier = value.strip()
        
        # If it's 9 digits, normalize to XXX-XXX-XXX format
        if identifier.isdigit() and len(identifier) == 9:
            identifier = f"{identifier[:3]}-{identifier[3:6]}-{identifier[6:9]}"
            
        from django.db.models import Q
        session = Session.objects.filter(
            Q(code=identifier) | Q(alias=identifier) | Q(host_identifier=identifier)
        ).first()

        if not session:
            raise serializers.ValidationError('Session not found. Check the code and try again.')

        if session.status == Session.Status.EXPIRED:
            raise serializers.ValidationError('This session has expired.')

        if session.status == Session.Status.CONNECTED:
            raise serializers.ValidationError('This session is already in use.')

        # Return the actual session object so views.py can use it
        self.validated_session = session
        return identifier

    def validate(self, attrs):
        attrs['session'] = self.validated_session
        return attrs


class SessionDetailSerializer(serializers.ModelSerializer):
    """Read-only serializer for session details."""

    class Meta:
        model = Session
        fields = ['id', 'code', 'status', 'host_identifier', 'alias', 'created_at', 'connected_at']
        read_only_fields = fields
