"""
REST API views for session management.
"""

from django.views.decorators.csrf import csrf_exempt
from rest_framework import status
from rest_framework.decorators import api_view, authentication_classes
from rest_framework.response import Response

from .models import Session
from .serializers import (
    SessionCreateSerializer,
    SessionJoinSerializer,
    SessionDetailSerializer,
)


@csrf_exempt
@api_view(['POST'])
@authentication_classes([])
def session_create(request):
    """
    Create or retrieve a remote support session.
    If host_identifier is provided and a session exists for it, reuse the code.
    """
    host_identifier = request.data.get('host_identifier')
    status_val = request.data.get('status', Session.Status.WAITING)

    if host_identifier:
        # Professional behavior: reuse the same code for the same machine
        session = Session.objects.filter(host_identifier=host_identifier).first()
        if session:
            session.status = status_val
            session.save(update_fields=['status'])
            return Response(SessionDetailSerializer(session).data, status=status.HTTP_200_OK)

    # Otherwise create a new one
    serializer = SessionCreateSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    session = serializer.save()
    return Response(
        SessionDetailSerializer(session).data,
        status=status.HTTP_201_CREATED,
    )


@csrf_exempt
@api_view(['POST'])
@authentication_classes([])
def session_join(request):
    """
    Join an existing session by code, alias, or IP address.

    Called by the Vue frontend when the support tech enters a session identifier.
    Returns session details and the WebSocket URL for signaling.
    """
    serializer = SessionJoinSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    session = serializer.validated_data['session']

    return Response({
        'session': SessionDetailSerializer(session).data,
        'ws_url': f'/ws/signaling/{session.code}/',
    })


@api_view(['GET'])
def session_status(request, code):
    """
    Check the status of a session.
    """
    try:
        session = Session.objects.get(code=code)
    except Session.DoesNotExist:
        return Response(
            {'error': 'Session not found.'},
            status=status.HTTP_404_NOT_FOUND,
        )

    return Response(SessionDetailSerializer(session).data)


@api_view(['GET'])
def session_list(request):
    """
    List all sessions, ordered by most recently created.
    Used by the frontend to populate the Recent Sessions grid.
    """
    sessions = Session.objects.all().order_by('-created_at')[:20]
    return Response(SessionDetailSerializer(sessions, many=True).data)


@csrf_exempt
@api_view(['PATCH'])
@authentication_classes([])
def session_rename(request, code):
    """
    Rename a session by setting its custom alias.
    """
    try:
        session = Session.objects.get(code=code)
    except Session.DoesNotExist:
        return Response(
            {'error': 'Session not found.'},
            status=status.HTTP_404_NOT_FOUND,
        )

    alias = request.data.get('alias', '')
    session.alias = alias
    session.save(update_fields=['alias'])
    return Response(SessionDetailSerializer(session).data)
