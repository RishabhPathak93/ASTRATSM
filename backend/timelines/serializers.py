"""timelines/serializers.py"""
from rest_framework import serializers

from accounts.serializers import UserSerializer
from .models import Timeline, TimelineApprovalRequest, TimelineMilestone


class TimelineMilestoneSerializer(serializers.ModelSerializer):
    class Meta:
        model = TimelineMilestone
        fields = ['id', 'timeline', 'title', 'due_date', 'completed', 'completed_at', 'created_at']
        read_only_fields = ['id', 'created_at']


class TimelineSerializer(serializers.ModelSerializer):
    assignee_details = UserSerializer(source='assignees', many=True, read_only=True)
    milestones = TimelineMilestoneSerializer(many=True, read_only=True)
    duration_days = serializers.ReadOnlyField()
    project_name = serializers.CharField(source='project.name', read_only=True)
    submitted_hours = serializers.DecimalField(source='submitted_hours_value', max_digits=10, decimal_places=2, read_only=True)
    approved_hours = serializers.DecimalField(source='approved_hours_value', max_digits=10, decimal_places=2, read_only=True)
    pending_hours = serializers.DecimalField(source='pending_hours_value', max_digits=10, decimal_places=2, read_only=True)
    remaining_hours = serializers.DecimalField(source='remaining_hours_value', max_digits=10, decimal_places=2, read_only=True)
    hours_progress = serializers.IntegerField(source='hours_progress_value', read_only=True)

    class Meta:
        model = Timeline
        fields = [
            'id', 'project', 'project_name', 'name', 'description',
            'start_date', 'end_date', 'status', 'progress', 'color',
            'hours_allocated', 'order', 'assignees', 'assignee_details', 'milestones',
            'duration_days', 'paused_at', 'hours_consumed',
            'submitted_hours', 'approved_hours', 'pending_hours', 'remaining_hours', 'hours_progress',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate(self, attrs):
        start = attrs.get('start_date', getattr(self.instance, 'start_date', None))
        end = attrs.get('end_date', getattr(self.instance, 'end_date', None))
        project = attrs.get('project', getattr(self.instance, 'project', None))
        assignees = attrs.get('assignees')
        if start and end and start > end:
            raise serializers.ValidationError({'end_date': 'End date must be after start date.'})
        if project and assignees is not None:
            invalid_assignees = [user.name for user in assignees if not project.resources.filter(pk=user.pk).exists()]
            if invalid_assignees:
                raise serializers.ValidationError({
                    'assignees': f'Assignees must belong to the selected project: {", ".join(invalid_assignees)}'
                })
        return attrs


class TimelineApprovalRequestSerializer(serializers.ModelSerializer):
    requested_by_name = serializers.CharField(source='requested_by.name', read_only=True)
    resolved_by_name = serializers.CharField(source='resolved_by.name', read_only=True)
    timeline_name = serializers.CharField(source='timeline.name', read_only=True)
    timeline_detail = serializers.SerializerMethodField()

    class Meta:
        model = TimelineApprovalRequest
        fields = [
            'id', 'timeline', 'timeline_name', 'timeline_detail',
            'request_type', 'status', 'reason', 'proposed_changes', 'admin_note',
            'requested_by', 'requested_by_name',
            'resolved_by', 'resolved_by_name',
            'created_at', 'resolved_at',
        ]
        read_only_fields = [
            'id', 'status', 'requested_by', 'resolved_by',
            'created_at', 'resolved_at', 'admin_note',
        ]

    def get_timeline_detail(self, obj):
        t = obj.timeline
        if not t:
            return None
        return {
            'name': t.name,
            'description': t.description,
            'status': t.status,
            'start_date': str(t.start_date) if t.start_date else '',
            'end_date': str(t.end_date) if t.end_date else '',
            'hours_allocated': t.hours_allocated,
            'hours_consumed': t.hours_consumed,
        }
