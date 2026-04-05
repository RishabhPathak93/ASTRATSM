"""notifications/views.py"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from .models import Notification
from .serializers import NotificationSerializer, ResourceNotificationPreferenceSerializer


class NotificationViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class   = NotificationSerializer
    permission_classes = [IsAuthenticated]
    filter_backends    = [DjangoFilterBackend]
    filterset_fields   = ['is_read', 'notif_type']

    def get_queryset(self):
        return (
            Notification.objects
            .filter(user=self.request.user)
            .select_related('project')
        )

    @action(detail=True, methods=['patch'])
    def mark_read(self, request, pk=None):
        notif = self.get_object()
        notif.is_read = True
        notif.save(update_fields=['is_read'])
        return Response({'is_read': True})

    @action(detail=False, methods=['post'])
    def mark_all_read(self, request):
        count = Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
        return Response({'marked_read': count})

    @action(detail=False, methods=['get'])
    def unread_count(self, request):
        return Response({'unread_count': Notification.objects.filter(user=request.user, is_read=False).count()})

    @action(detail=False, methods=['delete'])
    def clear_all(self, request):
        Notification.objects.filter(user=request.user).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ResourceNotifPreferenceViewSet(viewsets.ModelViewSet):
    """
    Admin/Manager can GET and SET notification preferences for any resource.
    GET  /notifications/preferences/          → list all resources + their prefs
    POST /notifications/preferences/          → create pref for a resource
    PATCH /notifications/preferences/<id>/   → update allowed_types
    GET  /notifications/preferences/all_types/ → list of all possible notif types
    """
    serializer_class   = ResourceNotificationPreferenceSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        from .models import ResourceNotificationPreference
        return ResourceNotificationPreference.objects.select_related('resource')

    def get_permissions(self):
        from accounts.permissions import IsAdminOrManager
        return [IsAdminOrManager()]

    def perform_create(self, serializer):
        serializer.save(updated_by=self.request.user)

    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)

    @action(detail=False, methods=['get'])
    def all_types(self, request):
        from .models import ALL_NOTIF_TYPES, Notification
        return Response([
            {'value': t, 'label': dict(Notification.Type.choices).get(t, t)}
            for t in ALL_NOTIF_TYPES
        ])

    @action(detail=False, methods=['get'])
    def for_resource(self, request):
        """GET /preferences/for_resource/?user_id=X — get or default prefs for one resource."""
        from .models import ResourceNotificationPreference, ALL_NOTIF_TYPES
        user_id = request.query_params.get('user_id')
        if not user_id:
            return Response({'detail': 'user_id required.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            pref = ResourceNotificationPreference.objects.get(resource_id=user_id)
            return Response(self.get_serializer(pref).data)
        except ResourceNotificationPreference.DoesNotExist:
            return Response({'resource': int(user_id), 'allowed_types': ALL_NOTIF_TYPES})