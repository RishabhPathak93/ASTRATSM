"""clients/views.py"""
import logging
from django.db.models import Q
from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend

from .models import Client, ClientContact
from .serializers import ClientSerializer, ClientContactSerializer
from accounts.permissions import IsAdminOrManager, IsAdminOrManagerOrReadOnly
from accounts.models import User
from notifications.utils import notify_admins_and_managers

logger = logging.getLogger('nexus')


class ClientViewSet(viewsets.ModelViewSet):
    serializer_class   = ClientSerializer
    permission_classes = [IsAdminOrManagerOrReadOnly]
    filter_backends    = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields   = ['status', 'industry']
    search_fields      = ['name', 'email', 'contact_person', 'industry']
    ordering_fields    = ['name', 'onboarded_at', 'status']

    def get_queryset(self):
        user = self.request.user
        base = Client.objects.select_related('onboarded_by').prefetch_related('contacts')
        if user.role == User.Role.ADMIN:
            return base.all()
        if user.role == User.Role.MANAGER:
            # Only clients linked to projects managed by this manager
            return base.filter(projects__manager=user).distinct()
        if user.role == User.Role.RESOURCE:
            return base.filter(projects__resources=user).distinct()
        if user.role == User.Role.CLIENT:
            return base.filter(Q(portal_user=user) | Q(projects__resources=user)).distinct()
        return base.none()

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx['request'] = self.request
        return ctx

    def perform_create(self, serializer):
        client = serializer.save(onboarded_by=self.request.user)
        logger.info('Client "%s" onboarded by %s', client.name, self.request.user.email)
        # Notify ALL admins + managers — no exclude, creator should also see it
        notify_admins_and_managers(
            notif_type='update',
            title=f'New client: {client.name}',
            message=f'"{client.name}" has been onboarded by {self.request.user.name}.',
            action_url=f'/clients/{client.id}',
        )

    def perform_update(self, serializer):
        old_status = self.get_object().status
        client = serializer.save()
        if old_status != client.status:
            notify_admins_and_managers(
                notif_type='status_change',
                title=f'Client status changed: {client.name}',
                message=f'"{client.name}" status changed to {client.get_status_display()}.',
                action_url=f'/clients/{client.id}',
            )

    @action(detail=True, methods=['get'])
    def projects(self, request, pk=None):
        client = self.get_object()
        from projects.serializers import ProjectListSerializer
        qs = client.projects.select_related('manager').prefetch_related('resources')
        return Response(ProjectListSerializer(qs, many=True, context={'request': request}).data)

    @action(detail=True, methods=['get', 'post'], url_path='contacts')
    def contacts(self, request, pk=None):
        client = self.get_object()
        if request.method == 'GET':
            return Response(ClientContactSerializer(client.contacts.all(), many=True).data)
        serializer = ClientContactSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(client=client)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class ClientContactViewSet(viewsets.ModelViewSet):
    queryset           = ClientContact.objects.select_related('client').all()
    serializer_class   = ClientContactSerializer
    permission_classes = [IsAdminOrManager]
    filter_backends    = [DjangoFilterBackend]
    filterset_fields   = ['client', 'is_primary']

    def get_queryset(self):
        user = self.request.user
        qs = super().get_queryset()
        if user.role == User.Role.ADMIN:
            return qs
        if user.role == User.Role.MANAGER:
            return qs.filter(client__projects__manager=user).distinct()
        return qs.none()
