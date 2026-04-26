from django.contrib import admin
from .models import Session


@admin.register(Session)
class SessionAdmin(admin.ModelAdmin):
    list_display = ['code', 'status', 'host_identifier', 'created_at', 'connected_at']
    list_filter = ['status']
    search_fields = ['code', 'host_identifier']
    readonly_fields = ['created_at', 'connected_at', 'disconnected_at']
