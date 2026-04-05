"""resources/serializers.py"""
from django.utils import timezone
from rest_framework import serializers
from .models import ResourceProfile, TimeEntry
from accounts.serializers import UserSerializer


class ResourceProfileSerializer(serializers.ModelSerializer):
    user_detail          = UserSerializer(source='user', read_only=True)
    manager_detail       = UserSerializer(source='manager', read_only=True)
    total_hours_logged   = serializers.ReadOnlyField()
    active_project_count = serializers.SerializerMethodField()

    class Meta:
        model  = ResourceProfile
        fields = [
            'id', 'user', 'user_detail',
            'resource_id', 'level', 'manager', 'manager_detail',
            'skills', 'hourly_rate', 'availability',
            'total_hours_logged', 'active_project_count',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_active_project_count(self, obj):
        return obj.user.assigned_projects.filter(
            status__in=['planning', 'in_progress', 'review', 'on_hold']
        ).count()

    def validate_resource_id(self, value):
        if not value:
            return value
        value = value.strip()
        qs = ResourceProfile.objects.filter(resource_id=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError('This Resource ID is already in use.')
        return value


class TimeEntrySerializer(serializers.ModelSerializer):
    resource_name = serializers.CharField(source='resource.user.name', read_only=True)
    project_name  = serializers.CharField(source='project.name', read_only=True)

    class Meta:
        model  = TimeEntry
        fields = [
            'id', 'resource', 'resource_name', 'project', 'project_name',
            'date', 'hours', 'description', 'approved', 'approved_by',
            'approved_at', 'created_at',
        ]
        read_only_fields = ['id', 'approved', 'approved_by', 'approved_at', 'created_at']
        extra_kwargs = {
            'resource': {'required': False},
        }

    def validate_hours(self, value):
        if value < 0.25:
            raise serializers.ValidationError('Minimum entry is 0.25 hours (15 minutes).')
        if value > 24:
            raise serializers.ValidationError('Cannot log more than 24 hours in a single entry.')
        return value

    def validate(self, attrs):
        request = self.context.get('request')
        user = getattr(request, 'user', None)
        if user and user.is_authenticated and user.role == 'resource' and 'resource' not in attrs:
            if not hasattr(user, 'resource_profile'):
                raise serializers.ValidationError('Your account does not have a resource profile.')
            attrs['resource'] = user.resource_profile

        resource = attrs.get('resource') or getattr(self.instance, 'resource', None)
        project = attrs.get('project') or getattr(self.instance, 'project', None)
        entry_date = attrs.get('date') or getattr(self.instance, 'date', None)

        if entry_date and entry_date > timezone.localdate():
            raise serializers.ValidationError({'date': 'Time entries cannot be logged in the future.'})

        if resource and project:
            is_project_resource = project.resources.filter(pk=resource.user_id).exists()
            is_phase_assignee = project.timelines.filter(assignees__pk=resource.user_id).exists()
            if not (is_project_resource or is_phase_assignee):
                raise serializers.ValidationError({'project': 'This resource is not assigned to the selected project or any of its phases.'})

        if user and user.is_authenticated and user.role == 'resource':
            if not hasattr(user, 'resource_profile'):
                raise serializers.ValidationError('Your account does not have a resource profile.')
            if resource and resource.pk != user.resource_profile.pk:
                raise serializers.ValidationError({'resource': 'You can only log time for yourself.'})

        return attrs
