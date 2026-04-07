import logging
from decimal import Decimal

from django.db.models import Case, Count, DecimalField, F, Q, Sum, Value, When
from django.db.models.functions import Coalesce, Greatest
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.models import User
from accounts.permissions import IsAdmin, IsAdminOrManager
from nexus.excel import workbook_response
from notifications.utils import email_no_reply, notify_admins_and_managers, notify_project_team, notify_user
from timelines.models import Timeline
from .models import ResourceProfile, TimeEntry
from .serializers import ResourceProfileSerializer, TimeEntrySerializer

logger = logging.getLogger('nexus')

ACTIVE_PROJECT_STATUSES = ['planning', 'in_progress', 'review', 'on_hold']
HOURS_OUTPUT = DecimalField(max_digits=10, decimal_places=2)


def _sync_timeline_hours(timeline_id):
    if not timeline_id:
        return
    timeline = Timeline.objects.filter(pk=timeline_id).first()
    if not timeline:
        return
    submitted = timeline.timeentries.aggregate(total=Coalesce(Sum('hours'), Value(0), output_field=HOURS_OUTPUT))['total'] or Decimal('0')
    Timeline.objects.filter(pk=timeline_id).update(hours_consumed=float(submitted))


def _timesheet_approvers(entry):
    recipients = []
    if entry.resource.manager and entry.resource.manager.is_active:
        recipients.append(entry.resource.manager)
    if entry.project.manager and entry.project.manager.is_active and entry.project.manager not in recipients:
        recipients.append(entry.project.manager)
    return recipients


def _timesheet_stakeholders(entry):
    admins = list(User.objects.filter(role=User.Role.ADMIN, is_active=True))
    recipients = [entry.resource.user, *_timesheet_approvers(entry), *admins]
    deduped = []
    seen = set()
    for user in recipients:
        if not user or not user.is_active or user.id in seen:
            continue
        seen.add(user.id)
        deduped.append(user)
    return deduped


def _send_timesheet_submission_email(entry):
    recipients = _timesheet_stakeholders(entry)
    scope = entry.timeline.name if entry.timeline else entry.project.name
    subject = f'Work log submitted: {entry.resource.user.name} on {entry.project.name}'
    email_no_reply(
        recipients,
        subject=subject,
        heading='A new work log has been submitted.',
        intro='AstraTSM recorded a new project work entry and updated the delivery hours for review.',
        details=[
            ('Resource', entry.resource.user.name),
            ('Project', entry.project.name),
            ('Phase', scope),
            ('Date', entry.date.isoformat()),
            ('Hours logged', entry.hours),
            ('Approval status', 'Pending manager/admin review'),
            ('Remaining phase hours', f"{max((entry.timeline.hours_allocated if entry.timeline else 0) - float(entry.timeline.hours_consumed if entry.timeline else 0), 0):.2f}h" if entry.timeline else 'See dashboard'),
        ],
        footer_note='This is an automated no-reply notification from AstraTSM. Please review the work log in the application.',
    )



def _send_timesheet_approval_email(entry, approver):
    subject = f'Time entry approved: {entry.project.name}'
    email_no_reply(
        [entry.resource.user],
        subject=subject,
        heading='Your submitted work log was approved.',
        intro='The hours you submitted are now marked as approved in AstraTSM.',
        details=[
            ('Resource', entry.resource.user.name),
            ('Project', entry.project.name),
            ('Phase', entry.timeline.name if entry.timeline else 'Project-level log'),
            ('Date', entry.date.isoformat()),
            ('Hours approved', entry.hours),
            ('Approved by', approver.name),
        ],
        footer_note='This is an automated no-reply notification from AstraTSM.',
    )


class ResourceProfileViewSet(viewsets.ModelViewSet):
    serializer_class = ResourceProfileSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['resource_id', 'user__name', 'user__email', 'manager__name']
    ordering_fields = ['user__name', 'hourly_rate', 'availability', 'created_at']

    def get_permissions(self):
        if self.action in ('create', 'update', 'partial_update', 'destroy', 'export'):
            return [IsAdmin()]
        return [IsAuthenticated()]

    def get_queryset(self):
        user = self.request.user
        qs = (
            ResourceProfile.objects
            .select_related('user', 'manager')
            .filter(user__role=User.Role.RESOURCE)
            .annotate(
                total_hours_value=Coalesce(Sum('timeentries__hours'), Value(0), output_field=HOURS_OUTPUT),
                approved_hours_value=Coalesce(Sum('timeentries__hours', filter=Q(timeentries__approved=True)), Value(0), output_field=HOURS_OUTPUT),
                pending_hours_value=Coalesce(Sum('timeentries__hours', filter=Q(timeentries__approved=False)), Value(0), output_field=HOURS_OUTPUT),
                active_project_count=Count(
                    'user__assigned_projects',
                    filter=Q(user__assigned_projects__status__in=ACTIVE_PROJECT_STATUSES),
                    distinct=True,
                ),
            )
        )
        qs = qs.order_by('user__name', 'id')
        if user.role == User.Role.ADMIN:
            return qs
        if user.role == User.Role.MANAGER:
            return qs.filter(manager=user)
        if user.role == User.Role.RESOURCE:
            return qs.filter(user=user)
        return qs.none()

    def perform_destroy(self, instance):
        user = instance.user
        logger.warning('Resource "%s" deleted by %s', user.email, self.request.user.email)
        user.delete()

    @action(detail=False, methods=['get'])
    def export(self, request):
        resources = self.filter_queryset(self.get_queryset()).order_by('user__name')
        rows = [
            [
                resource.resource_id or '',
                resource.user.name,
                resource.user.email,
                resource.level or '',
                resource.manager.name if resource.manager else '',
                resource.hourly_rate,
                resource.availability,
                resource.active_project_count or 0,
                resource.total_hours_value or 0,
                resource.approved_hours_value or 0,
                resource.pending_hours_value or 0,
                ', '.join(resource.skills or []),
            ]
            for resource in resources
        ]
        return workbook_response(
            filename='resources.xlsx',
            sheet_name='Resources',
            headers=['Resource ID', 'Name', 'Email', 'Level', 'Manager', 'Hourly Rate', 'Availability %', 'Active Projects', 'Logged Hours', 'Approved Hours', 'Pending Hours', 'Skills'],
            rows=rows,
        )

    @action(detail=True, methods=['get'])
    def time_entries(self, request, pk=None):
        profile = self.get_object()
        entries = profile.timeentries.select_related('project', 'timeline').order_by('-date')
        return Response(TimeEntrySerializer(entries, many=True).data)

    @action(detail=True, methods=['patch'], permission_classes=[IsAdminOrManager])
    def set_availability(self, request, pk=None):
        profile = self.get_object()
        try:
            value = int(request.data.get('availability', -1))
            assert 0 <= value <= 100
        except (TypeError, ValueError, AssertionError):
            return Response({'detail': 'availability must be an integer 0-100.'}, status=status.HTTP_400_BAD_REQUEST)
        old_value = profile.availability
        profile.availability = value
        profile.save(update_fields=['availability', 'updated_at'])
        if old_value != value:
            notify_user(
                user=profile.user,
                notif_type='update',
                title='Your availability has been updated',
                message=f'Your availability has been set to {value}% by {request.user.name}.',
                action_url='/profile',
            )
        return Response({'availability': profile.availability})


class TimeEntryViewSet(viewsets.ModelViewSet):
    queryset = TimeEntry.objects.select_related('resource__user', 'resource__manager', 'project__manager', 'timeline', 'approved_by')
    serializer_class = TimeEntrySerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['resource', 'project', 'timeline', 'date', 'approved']
    ordering_fields = ['date', 'hours']

    def get_queryset(self):
        user = self.request.user
        qs = super().get_queryset()
        if user.role == User.Role.ADMIN:
            return qs
        if user.role == User.Role.MANAGER:
            managed_projects = user.managed_projects.values_list('id', flat=True)
            return qs.filter(project_id__in=managed_projects)
        try:
            return qs.filter(resource=user.resource_profile)
        except ResourceProfile.DoesNotExist as exc:
            raise PermissionDenied('Your account does not have a resource profile.') from exc

    def perform_create(self, serializer):
        user = self.request.user
        if user.role == User.Role.RESOURCE:
            try:
                entry = serializer.save(resource=user.resource_profile)
            except ResourceProfile.DoesNotExist as exc:
                raise PermissionDenied('Your account does not have a resource profile.') from exc
        else:
            entry = serializer.save()
        _sync_timeline_hours(entry.timeline_id)
        notify_admins_and_managers(
            notif_type='update',
            title=f'Time entry submitted by {entry.resource.user.name}',
            message=f'{entry.resource.user.name} logged {entry.hours}h on "{entry.project.name}"' + (f' for phase "{entry.timeline.name}"' if entry.timeline else '') + f' on {entry.date}.',
            project=entry.project,
            action_url='/resources',
        )
        notify_user(
            user=entry.resource.user,
            notif_type='update',
            title='Work log submitted',
            message=f'Your {entry.hours}h entry for "{entry.project.name}" has been recorded and sent for review.',
            project=entry.project,
            action_url='/timelines',
        )
        entry.timeline = TimeEntry.objects.select_related('timeline').get(pk=entry.pk).timeline
        _send_timesheet_submission_email(entry)

    def perform_update(self, serializer):
        previous = self.get_object()
        old_timeline_id = previous.timeline_id
        entry = serializer.save()
        _sync_timeline_hours(old_timeline_id)
        _sync_timeline_hours(entry.timeline_id)

    def perform_destroy(self, instance):
        timeline_id = instance.timeline_id
        instance.delete()
        _sync_timeline_hours(timeline_id)

    @action(detail=True, methods=['patch'], permission_classes=[IsAdminOrManager])
    def approve(self, request, pk=None):
        entry = self.get_object()
        if entry.approved:
            return Response({'detail': 'Already approved.'}, status=status.HTTP_400_BAD_REQUEST)
        entry.approved = True
        entry.approved_by = request.user
        entry.approved_at = timezone.now()
        entry.save(update_fields=['approved', 'approved_by', 'approved_at'])
        _sync_timeline_hours(entry.timeline_id)
        notify_user(
            user=entry.resource.user,
            notif_type='update',
            title='Time entry approved',
            message=f'Your {entry.hours}h on "{entry.project.name}" ({entry.date}) was approved by {request.user.name}.',
            project=entry.project,
            action_url='/resources',
        )
        _send_timesheet_approval_email(entry, request.user)
        return Response({'approved': True, 'approved_by': request.user.name})
