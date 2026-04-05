"""chat/serializers.py"""
import os
from rest_framework import serializers
from django.conf import settings
from .models import ChatRoom, Message
from accounts.serializers import UserSerializer


class MessageSerializer(serializers.ModelSerializer):
    sender_detail  = UserSerializer(source='sender', read_only=True)
    attachment_url  = serializers.SerializerMethodField()
    attachment_name = serializers.SerializerMethodField()

    class Meta:
        model  = Message
        fields = [
            'id', 'room', 'sender', 'sender_detail', 'text',
            'msg_type', 'attachment', 'attachment_url', 'attachment_name',
            'is_edited', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'sender', 'is_edited', 'created_at', 'updated_at']
        extra_kwargs = {'attachment': {'write_only': True, 'required': False}}

    def get_attachment_url(self, obj):
        """Return absolute URL using BACKEND_URL from settings so other devices can access it."""
        if obj.attachment and hasattr(obj.attachment, 'url'):
            from django.conf import settings as django_settings
            base = django_settings.BACKEND_URL.rstrip('/')
            return f"{base}{obj.attachment.url}"
        return None

    def get_attachment_name(self, obj):
        """Extract original filename from the attachment path."""
        if obj.attachment and hasattr(obj.attachment, 'name'):
            import os
            return os.path.basename(obj.attachment.name)
        return obj.text or None

    def validate_text(self, value):
        if self.initial_data.get('msg_type', 'text') == 'text' and not value.strip():
            raise serializers.ValidationError('Message text cannot be empty.')
        if len(value) > 4000:
            raise serializers.ValidationError('Message too long (max 4000 chars).')
        return value

    def validate_attachment(self, value):
        if value:
            ext = os.path.splitext(value.name)[1].lower()
            allowed = settings.ALLOWED_IMAGE_EXTENSIONS + settings.ALLOWED_DOCUMENT_EXTENSIONS
            if ext not in allowed:
                raise serializers.ValidationError('File type not supported.')
            if value.size > settings.MAX_DOCUMENT_SIZE_MB * 1024 * 1024:
                raise serializers.ValidationError(f'File must be under {settings.MAX_DOCUMENT_SIZE_MB} MB.')
        return value


class ChatRoomSerializer(serializers.ModelSerializer):
    member_details = UserSerializer(source='members', many=True, read_only=True)
    last_message   = serializers.SerializerMethodField()
    unread_count   = serializers.SerializerMethodField()
    project_name   = serializers.CharField(source='project.name', read_only=True)

    class Meta:
        model  = ChatRoom
        fields = [
            'id', 'room_type', 'project', 'project_name', 'name',
            'members', 'member_details', 'last_message', 'unread_count', 'created_at',
        ]
        read_only_fields = ['id', 'created_at']

    def get_last_message(self, obj):
        msg = obj.last_message
        if not msg:
            return None
        return {
            'id':          msg.id,
            'text':        msg.text,
            'sender_name': msg.sender.name if msg.sender else '',
            'created_at':  msg.created_at.isoformat(),
        }

    def get_unread_count(self, obj):
        user = self.context['request'].user
        return obj.messages.exclude(read_by=user).exclude(sender=user).count()