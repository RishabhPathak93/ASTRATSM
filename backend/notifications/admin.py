"""notifications/admin.py"""
from django.contrib import admin
from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display  = ['user', 'notif_type', 'title', 'is_read', 'created_at']
    list_filter   = ['notif_type', 'is_read']
    search_fields = ['user__name', 'title']
    readonly_fields = ['created_at']

    def has_add_permission(self, request):
        return False  # notifications are system-generated only
