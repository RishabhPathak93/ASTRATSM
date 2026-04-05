"""chat/admin.py"""
from django.contrib import admin
from .models import ChatRoom, Message


@admin.register(ChatRoom)
class ChatRoomAdmin(admin.ModelAdmin):
    list_display      = ['__str__', 'room_type', 'created_at']
    filter_horizontal = ['members']
    readonly_fields   = ['created_at']


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display    = ['sender', 'room', 'msg_type', 'is_edited', 'created_at']
    list_filter     = ['msg_type']
    search_fields   = ['text', 'sender__name']
    readonly_fields = ['created_at', 'updated_at']

    def has_add_permission(self, request):
        return False  # messages only created via WS or API
