"""accounts/views.py"""
import logging
from rest_framework import generics, status, viewsets, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.throttling import AnonRateThrottle
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError
from django_filters.rest_framework import DjangoFilterBackend

from .models import User, RolePermission
from .serializers import (
    CustomTokenObtainPairSerializer, UserSerializer, UserCreateSerializer,
    UserUpdateSerializer, ChangePasswordSerializer, AdminChangeRoleSerializer,
    RolePermissionSerializer,
)
from .permissions import IsAdmin, IsAdminOrManager

logger = logging.getLogger('nexus')


class LoginThrottle(AnonRateThrottle):
    rate = '10/min'


class LoginView(TokenObtainPairView):
    permission_classes = [AllowAny]
    serializer_class   = CustomTokenObtainPairSerializer
    throttle_classes   = [LoginThrottle]


class LogoutView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            token = RefreshToken(request.data['refresh'])
            token.blacklist()
            logger.info('User %s logged out', request.user.email)
            return Response({'detail': 'Successfully logged out.'}, status=status.HTTP_200_OK)
        except KeyError:
            return Response(
                {'detail': 'refresh token is required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except TokenError as e:
            return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class MeView(generics.RetrieveUpdateAPIView):
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        return UserUpdateSerializer if self.request.method in ('PUT', 'PATCH') else UserSerializer

    def get_object(self):
        return self.request.user

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx['request'] = self.request
        return ctx


class ChangePasswordView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class   = ChangePasswordSerializer

    def post(self, request):
        serializer = self.get_serializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        request.user.set_password(serializer.validated_data['new_password'])
        request.user.save(update_fields=['password', 'updated_at'])
        logger.info('Password changed for user %s', request.user.email)
        return Response({'detail': 'Password changed successfully.'}, status=status.HTTP_200_OK)


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all().order_by('name')
    filter_backends  = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['role', 'is_active', 'department']
    search_fields    = ['name', 'email', 'department']
    ordering_fields  = ['name', 'date_joined', 'role', 'last_seen']

    def get_permissions(self):
        if self.action in ('list', 'retrieve'):
            return [IsAuthenticated()]
        return [IsAdmin()]

    def get_serializer_class(self):
        if self.action == 'create':
            return UserCreateSerializer
        if self.action in ('update', 'partial_update'):
            return UserUpdateSerializer
        return UserSerializer

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx['request'] = self.request
        return ctx

    def destroy(self, request, *args, **kwargs):
        user = self.get_object()
        if user == request.user:
            return Response(
                {'detail': 'You cannot delete your own account.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        logger.warning('Admin %s deleted user %s', request.user.email, user.email)
        return super().destroy(request, *args, **kwargs)

    @action(detail=True, methods=['patch'], permission_classes=[IsAdmin])
    def toggle_status(self, request, pk=None):
        user = self.get_object()
        if user == request.user:
            return Response(
                {'detail': 'You cannot deactivate your own account.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        user.is_active = not user.is_active
        user.save(update_fields=['is_active', 'updated_at'])
        logger.warning('Admin %s toggled status of %s → is_active=%s',
                       request.user.email, user.email, user.is_active)
        return Response({'id': user.id, 'is_active': user.is_active})

    @action(detail=True, methods=['patch'], permission_classes=[IsAdmin],
            serializer_class=AdminChangeRoleSerializer)
    def change_role(self, request, pk=None):
        user = self.get_object()
        if user == request.user:
            return Response(
                {'detail': 'You cannot change your own role.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer = AdminChangeRoleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        old_role  = user.role
        user.role = serializer.validated_data['role']
        user.save(update_fields=['role', 'updated_at'])
        logger.warning('Admin %s changed role of %s: %s → %s',
                       request.user.email, user.email, old_role, user.role)
        return Response(UserSerializer(user, context={'request': request}).data)


class RolePermissionViewSet(viewsets.ModelViewSet):
    queryset           = RolePermission.objects.all().order_by('role')
    serializer_class   = RolePermissionSerializer
    permission_classes = [IsAdminOrManager]
    http_method_names  = ['get', 'put', 'patch', 'head', 'options']  # no create/delete

    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)
        logger.info('Role permissions updated for %s by %s',
                    serializer.instance.role, self.request.user.email)
