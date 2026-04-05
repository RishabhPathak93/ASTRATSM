"""notifications/serializers.py"""
from rest_framework import serializers
from .models import Notification, ResourceNotificationPreference, ALL_NOTIF_TYPES


class NotificationSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source='project.name', read_only=True)

    class Meta:
        model  = Notification
        fields = ['id', 'notif_type', 'title', 'message', 'is_read',
                  'project', 'project_name', 'action_url', 'created_at']
        read_only_fields = ['id', 'created_at']


class ResourceNotificationPreferenceSerializer(serializers.ModelSerializer):
    resource_name = serializers.CharField(source='resource.name', read_only=True)

    class Meta:
        model  = ResourceNotificationPreference
        fields = ['id', 'resource', 'resource_name', 'allowed_types', 'updated_at']
        read_only_fields = ['id', 'updated_at']