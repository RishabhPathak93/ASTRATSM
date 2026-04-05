"""projects/views.py"""
import logging
from django.db import transaction
from django.utils import timezone
from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend

from .models import Project, ProjectUpdate, ProjectDocument, ProjectApprovalRequest
from .serializers import (
    ProjectListSerializer, ProjectDetailSerializer,
    ProjectUpdateSerializer, ProjectDocumentSerializer,
    ProjectApprovalRequestSerializer,
)
from accounts.permissions import IsAdminOrManager, IsAdmin
from accounts.models import User
from notifications.utils import notify_project_team

logger = logging.getLogger('nexus')


def _project_team(project, exclude=None):
    seen, result = set(), []
    candidates = list(project.resources.filter(is_active=True))
    if project.manager:
        candidates.append(project.manager)
    for u in candidates:
        if u.id not in seen and u != exclude:
            seen.add(u.id)
            result.append(u)
    return result


def _notify_admins(title, message, action_url=''):
    admins = list(User.objects.filter(role=User.Role.ADMIN, is_active=True))
    if admins:
        notify_project_team(users=admins, notif_type='update', title=title, message=message, action_url=action_url)


class ProjectViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    filter_backends    = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields   = ['status', 'priority', 'client', 'manager']
    search_fields      = ['name', 'description']
    ordering_fields    = ['name', 'created_at', 'end_date', 'priority', 'progress', 'budget']

    def get_queryset(self):
        user = self.request.user
        base = (
            Project.objects
            .select_related('client', 'manager', 'created_by')
            .prefetch_related('resources', 'updates', 'documents')
        )
        if user.role == User.Role.ADMIN:
            return base.all()
        if user.role == User.Role.MANAGER:
            # Managers see only their assigned projects
            return base.filter(manager=user)
        if user.role == User.Role.RESOURCE:
            return base.filter(resources=user)
        return base.none()

    def get_serializer_class(self):
        return ProjectListSerializer if self.action == 'list' else ProjectDetailSerializer

    def get_permissions(self):
        # Only admin can create, directly edit, or delete
        if self.action in ('create', 'update', 'partial_update', 'destroy'):
            return [IsAdmin()]
        return [IsAuthenticated()]

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx['request'] = self.request
        return ctx

    def perform_create(self, serializer):
        project = serializer.save(created_by=self.request.user)
        logger.info('Project "%s" created by %s', project.name, self.request.user.email)
        recipients = list(User.objects.filter(role__in=[User.Role.ADMIN, User.Role.MANAGER], is_active=True))
        for r in project.resources.filter(is_active=True):
            if r not in recipients:
                recipients.append(r)
        notify_project_team(
            users=recipients, notif_type='project_assigned',
            title=f'New project: {project.name}',
            message=f'Project "{project.name}" has been created' + (f' for client {project.client.name}.' if project.client else '.'),
            project=project, action_url=f'/projects/{project.id}',
        )

    def perform_update(self, serializer):
        old_status   = self.get_object().status
        old_progress = self.get_object().progress
        project      = serializer.save()
        if old_status != project.status:
            notify_project_team(
                users=_project_team(project), notif_type='status_change',
                title=f'Project status changed: {project.name}',
                message=f'"{project.name}" is now {project.get_status_display()}.',
                project=project, action_url=f'/projects/{project.id}',
            )
        if old_progress != 100 and project.progress == 100:
            notify_project_team(
                users=_project_team(project), notif_type='timeline_complete',
                title=f'Project completed: {project.name}',
                message=f'"{project.name}" reached 100% progress.',
                project=project, action_url=f'/projects/{project.id}',
            )

    def perform_destroy(self, instance):
        name = instance.name
        notify_project_team(users=_project_team(instance), notif_type='status_change', title='Project deleted', message=f'The project "{name}" has been removed.')
        instance.delete()
        logger.warning('Project "%s" deleted by %s', name, self.request.user.email)

    @action(detail=True, methods=['post'], permission_classes=[IsAdminOrManager])
    def add_update(self, request, pk=None):
        project    = self.get_object()
        serializer = ProjectUpdateSerializer(data={**request.data, 'project': project.id})
        serializer.is_valid(raise_exception=True)
        serializer.save(author=request.user, project=project)
        notify_project_team(users=_project_team(project), notif_type='update', title=f'Update on "{project.name}"', message=request.data.get('content', '')[:140], project=project, action_url=f'/projects/{project.id}')
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def upload_document(self, request, pk=None):
        project    = self.get_object()
        serializer = ProjectDocumentSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save(uploaded_by=request.user, project=project)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['patch'], permission_classes=[IsAdminOrManager])
    def update_progress(self, request, pk=None):
        project = self.get_object()
        try:
            value = int(request.data.get('progress'))
            if not (0 <= value <= 100): raise ValueError
        except (ValueError, TypeError):
            return Response({'detail': 'progress must be 0-100.'}, status=status.HTTP_400_BAD_REQUEST)
        old = project.progress
        project.progress = value
        project.save(update_fields=['progress', 'updated_at'])
        if old != 100 and value == 100:
            notify_project_team(users=_project_team(project), notif_type='timeline_complete', title=f'Project completed: {project.name}', message=f'"{project.name}" reached 100%.', project=project, action_url=f'/projects/{project.id}')
        return Response({'id': project.id, 'progress': project.progress})

    @action(detail=True, methods=['post'], permission_classes=[IsAdminOrManager])
    def assign_resource(self, request, pk=None):
        project = self.get_object()
        try:
            user = User.objects.get(pk=request.data.get('user_id'), role=User.Role.RESOURCE, is_active=True)
        except User.DoesNotExist:
            return Response({'detail': 'Active resource user not found.'}, status=status.HTTP_404_NOT_FOUND)
        project.resources.add(user)
        notify_project_team(users=[user], notif_type='project_assigned', title=f'Added to project: {project.name}', message=f'You have been assigned to "{project.name}".', project=project, action_url=f'/projects/{project.id}')
        return Response({'detail': f'{user.name} added to project.'})

    @action(detail=True, methods=['post'], permission_classes=[IsAdminOrManager])
    def remove_resource(self, request, pk=None):
        project = self.get_object()
        try:
            user = User.objects.get(pk=request.data.get('user_id'))
        except User.DoesNotExist:
            return Response({'detail': 'User not found.'}, status=status.HTTP_404_NOT_FOUND)
        project.resources.remove(user)
        notify_project_team(users=[user], notif_type='status_change', title=f'Removed from project: {project.name}', message=f'You have been removed from "{project.name}".', project=project)
        return Response({'detail': f'{user.name} removed from project.'})


class ProjectApprovalViewSet(viewsets.ModelViewSet):
    """
    - Manager submits a request (just reason + type, no changes yet)
    - Admin approves/rejects
    - On approval of EDIT: manager gets notified, goes to Approvals tab,
      fills in changes and calls apply_edit to actually update the project
    - On approval of DELETE: project is deleted immediately
    """
    serializer_class   = ProjectApprovalRequestSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        qs = ProjectApprovalRequest.objects.select_related('project', 'requested_by', 'resolved_by')
        if user.role == User.Role.ADMIN:
            return qs.all()
        if user.role == User.Role.MANAGER:
            return (qs.filter(project__manager=user) | qs.filter(requested_by=user)).distinct()
        # Resources see their own requests
        return qs.filter(requested_by=user)

    def get_permissions(self):
        if self.action in ('update', 'partial_update', 'destroy'):
            return [IsAdmin()]
        return [IsAuthenticated()]

    def perform_create(self, serializer):
        user = self.request.user
        project = serializer.validated_data.get('project')
        if user.role not in (User.Role.MANAGER, User.Role.ADMIN):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('Only managers can submit approval requests.')
        if user.role == User.Role.MANAGER and project and project.manager_id != user.pk:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('You can only request approvals for projects you manage.')
        if project:
            existing = ProjectApprovalRequest.objects.filter(
                project=project,
                requested_by=user,
                request_type=serializer.validated_data.get('request_type'),
                status=ProjectApprovalRequest.Status.PENDING,
            ).first()
            if existing:
                from rest_framework.exceptions import PermissionDenied
                raise PermissionDenied('You already have a pending request of this type for this project.')
        req = serializer.save(requested_by=user, proposed_changes={})
        project_name = req.project.name if req.project else 'Unknown'
        logger.info('Approval request %s (%s) by %s', req.id, req.request_type, user.email)
        _notify_admins(
            title=f'Approval needed: {req.request_type.upper()} — {project_name}',
            message=f'{user.name} wants to {req.request_type} "{project_name}". Reason: {req.reason or "No reason given."}',
            action_url='/approvals',
        )

    @action(detail=True, methods=['post'], permission_classes=[IsAdmin])
    def approve(self, request, pk=None):
        req = self.get_object()
        if req.status != ProjectApprovalRequest.Status.PENDING:
            return Response({'detail': 'Already resolved.'}, status=status.HTTP_400_BAD_REQUEST)

        req.status      = ProjectApprovalRequest.Status.APPROVED
        req.resolved_by = request.user
        req.resolved_at = timezone.now()
        req.admin_note  = request.data.get('admin_note', '')
        req.save()

        project = req.project

        # Save refs before any deletion
        requesting_manager = req.requested_by
        project_name       = project.name if project else 'project'
        admin_note_msg     = req.admin_note

        # DELETE: apply immediately
        if req.request_type == ProjectApprovalRequest.RequestType.DELETE and project:
            notify_project_team(users=_project_team(project), notif_type='status_change', title='Project deleted', message=f'The project "{project_name}" has been removed.')
            project.delete()
            # Notify manager after deletion (req still intact since FK is now SET_NULL)
            if requesting_manager:
                notify_project_team(
                    users=[requesting_manager], notif_type='update',
                    title=f'Delete approved — {project_name}',
                    message=f'Your delete request for "{project_name}" was approved and the project has been removed.' + (f' Note: {admin_note_msg}' if admin_note_msg else ''),
                    action_url='/approvals',
                )
            return Response({'detail': 'Approved. Project deleted.'})

        # EDIT: notify manager to go apply their changes from Approvals tab
        if requesting_manager:
            notify_project_team(
                users=[requesting_manager], notif_type='update',
                title=f'Edit approved — {project_name}',
                message=f'Your edit request for "{project_name}" was approved. Go to the Approvals tab in the sidebar to apply your changes.' + (f' Note: {admin_note_msg}' if admin_note_msg else ''),
                action_url='/approvals',
            )

        return Response({'detail': 'Approved. Manager can now apply the edit.'})

    @action(detail=True, methods=['post'], permission_classes=[IsAdmin])
    def reject(self, request, pk=None):
        req = self.get_object()
        if req.status != ProjectApprovalRequest.Status.PENDING:
            return Response({'detail': 'Already resolved.'}, status=status.HTTP_400_BAD_REQUEST)
        req.status      = ProjectApprovalRequest.Status.REJECTED
        req.resolved_by = request.user
        req.resolved_at = timezone.now()
        req.admin_note  = request.data.get('admin_note', '')
        req.save()
        if req.requested_by:
            project_name = req.project.name if req.project else 'project'
            notify_project_team(
                users=[req.requested_by], notif_type='update',
                title=f'Request rejected — {project_name}',
                message=f'Your {req.request_type} request for "{project_name}" was rejected.' + (f' Reason: {req.admin_note}' if req.admin_note else ''),
                action_url='/approvals',
            )
        return Response({'detail': 'Rejected.'})

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def apply_edit(self, request, pk=None):
        """
        Manager calls this after their edit request is approved.
        They pass the actual field changes they want to apply.
        Can only be called once (marks request as 'applied' via a flag).
        """
        req = self.get_object()
        user = request.user

        # Only the requesting manager can apply
        if req.requested_by != user:
            return Response({'detail': 'You did not make this request.'}, status=status.HTTP_403_FORBIDDEN)
        if req.request_type != ProjectApprovalRequest.RequestType.EDIT:
            return Response({'detail': 'This is not an edit request.'}, status=status.HTTP_400_BAD_REQUEST)
        if req.status != ProjectApprovalRequest.Status.APPROVED:
            return Response({'detail': 'Request not approved yet.'}, status=status.HTTP_400_BAD_REQUEST)
        # Prevent double-apply by checking proposed_changes is empty (initial) or checking a sentinel
        if req.proposed_changes.get('_applied'):
            return Response({'detail': 'Already applied.'}, status=status.HTTP_400_BAD_REQUEST)

        project = req.project
        if not project:
            return Response({'detail': 'Project not found.'}, status=status.HTTP_404_NOT_FOUND)

        allowed_fields = {
            'name', 'description', 'status', 'priority', 'start_date', 'end_date',
            'resource_l1', 'resource_l2', 'resource_l3', 'resource_l4', 'hours', 'activity',
        }
        payload = {key: value for key, value in request.data.items() if key in allowed_fields}

        if not payload:
            return Response({'detail': 'No valid fields to update.'}, status=status.HTTP_400_BAD_REQUEST)
        serializer = ProjectDetailSerializer(project, data=payload, partial=True, context={'request': request})
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            serializer.save()
            req.proposed_changes = {**serializer.validated_data, '_applied': True}
            req.save(update_fields=['proposed_changes'])

        notify_project_team(
            users=_project_team(project), notif_type='status_change',
            title=f'Project updated: {project.name}',
            message=f'"{project.name}" was updated by {user.name}.',
            project=project, action_url=f'/projects/{project.id}',
        )

        return Response({'detail': 'Edit applied successfully.'})

    @action(detail=False, methods=['get'])
    def pending_count(self, request):
        """
        For admin: count pending requests.
        For manager: count approved-but-unapplied edit requests.
        """
        user = request.user
        if user.role == User.Role.ADMIN:
            count = ProjectApprovalRequest.objects.filter(
                status=ProjectApprovalRequest.Status.PENDING
            ).count()
        elif user.role == User.Role.MANAGER:
            count = ProjectApprovalRequest.objects.filter(
                requested_by=user,
                request_type=ProjectApprovalRequest.RequestType.EDIT,
                status=ProjectApprovalRequest.Status.APPROVED,
            ).exclude(proposed_changes__has_key='_applied').count()
        else:
            count = 0
        return Response({'count': count})

    @action(detail=False, methods=['post'])
    def mark_all_read(self, request):
        """
        Admin: marks all pending requests as 'seen' (just returns updated count=0 for badge).
        Manager: marks all approved requests as seen.
        Both store a server-side last_read_at timestamp per user via a simple approach.
        We store it in the user's session/cache — here we just return success and
        the frontend handles the badge reset via localStorage.
        """
        return Response({'detail': 'Marked as read.', 'count': 0})
