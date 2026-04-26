"""
URL configuration for the signaling REST API.
"""

from django.urls import path
from . import views

urlpatterns = [
    path('sessions/', views.session_list, name='session-list'),
    path('session/create/', views.session_create, name='session-create'),
    path('session/join/', views.session_join, name='session-join'),
    path('session/<str:code>/status/', views.session_status, name='session-status'),
    path('session/<str:code>/rename/', views.session_rename, name='session-rename'),
]
