"""resources/views.py"""
import logging
from django.db.models import Q
from django.utils import timezone
from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend

from .models import ResourceProfile, TimeEntry
from .serializers import ResourceProfileSerializer, TimeEntrySerializer
from accounts.permissions import IsAdminOrManager
from accounts.models import User
from notifications.utils import notify_user, notify_admins_and_managers

logger = logging.getLogger('nexus')


class ResourceProfileViewSet(viewsets.ModelViewSet):
    queryset = ResourceProfile.objects.select_related('user', 'manager').filter(user__role='resource')
    serializer_class   = ResourceProfileSerializer
    filter_backends    = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields      = ['user__name', 'job_title']
    ordering_fields    = ['user__name', 'hourly_rate', 'availability']

    def get_permissions(self):
        if self.action in ('create', 'update', 'partial_update', 'destroy'):
            return [IsAdminOrManager()]
        return [IsAuthenticated()]

    def get_queryset(self):
        user = self.request.user
        qs = super().get_queryset()
        if user.role == User.Role.ADMIN:
            return qs
        if user.role == User.Role.MANAGER:
            return qs.filter(Q(manager=user) | Q(user__assigned_projects__manager=user)).distinct()
        if user.role == User.Role.RESOURCE:
            return qs.filter(user=user)
        return qs.none()

    @action(detail=True, methods=['get'])
    def time_entries(self, request, pk=None):
        profile = self.get_object()
        entries = profile.timeentries.select_related('project').order_by('-date')
        return Response(TimeEntrySerializer(entries, many=True).data)

    @action(detail=True, methods=['patch'], permission_classes=[IsAdminOrManager])
    def set_availability(self, request, pk=None):
        profile = self.get_object()
        try:
            value = int(request.data.get('availability', -1))
            assert 0 <= value <= 100
        except (TypeError, ValueError, AssertionError):
            return Response({'detail': 'availability must be an integer 0–100.'}, status=status.HTTP_400_BAD_REQUEST)
        old_value = profile.availability
        profile.availability = value
        profile.save(update_fields=['availability', 'updated_at'])
        # Tell the resource their availability changed
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
    queryset = TimeEntry.objects.select_related('resource__user', 'project', 'approved_by')
    serializer_class   = TimeEntrySerializer
    permission_classes = [IsAuthenticated]
    filter_backends    = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields   = ['resource', 'project', 'date', 'approved']
    ordering_fields    = ['date', 'hours']

    def get_queryset(self):
        user = self.request.user
        qs   = super().get_queryset()
        if user.role == User.Role.ADMIN:
            return qs.filter(approved=True)
        if user.role == User.Role.MANAGER:
            managed_projects = user.managed_projects.values_list('id', flat=True)
            return qs.filter(project_id__in=managed_projects)
        try:
            return qs.filter(resource=user.resource_profile)
        except ResourceProfile.DoesNotExist:
            return qs.none()

    def perform_create(self, serializer):
        user = self.request.user
        if user.role == User.Role.RESOURCE:
            try:
                entry = serializer.save(resource=user.resource_profile)
            except ResourceProfile.DoesNotExist as exc:
                raise PermissionDenied('Your account does not have a resource profile.') from exc
        else:
            entry = serializer.save()
        # Notify admins + managers that a time entry needs review
        notify_admins_and_managers(
            notif_type='update',
            title=f'Time entry submitted by {entry.resource.user.name}',
            message=f'{entry.resource.user.name} logged {entry.hours}h on "{entry.project.name}" on {entry.date}.',
            project=entry.project,
            action_url='/resources',
        )

    @action(detail=True, methods=['patch'], permission_classes=[IsAdminOrManager])
    def approve(self, request, pk=None):
        entry = self.get_object()
        if entry.approved:
            return Response({'detail': 'Already approved.'}, status=status.HTTP_400_BAD_REQUEST)
        entry.approved    = True
        entry.approved_by = request.user
        entry.approved_at = timezone.now()
        entry.save(update_fields=['approved', 'approved_by', 'approved_at'])
        # Tell the resource their hours were approved
        notify_user(
            user=entry.resource.user,
            notif_type='update',
            title='Time entry approved',
            message=f'Your {entry.hours}h on "{entry.project.name}" ({entry.date}) was approved by {request.user.name}.',
            project=entry.project,
            action_url='/resources',
        )
        return Response({'approved': True, 'approved_by': request.user.name})
