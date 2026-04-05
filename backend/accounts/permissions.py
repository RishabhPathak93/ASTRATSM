"""accounts/permissions.py"""
from rest_framework.permissions import BasePermission, SAFE_METHODS
from .models import User


class IsAdmin(BasePermission):
    message = 'Only administrators can perform this action.'

    def has_permission(self, request, view):
        return (
            request.user and
            request.user.is_authenticated and
            request.user.role == User.Role.ADMIN
        )


class IsAdminOrManager(BasePermission):
    message = 'Only admins or project managers can perform this action.'

    def has_permission(self, request, view):
        return (
            request.user and
            request.user.is_authenticated and
            request.user.role in (User.Role.ADMIN, User.Role.MANAGER)
        )


class IsAdminOrManagerOrReadOnly(BasePermission):
    """Admins/managers get full write access; others are read-only."""
    message = 'Only admins or project managers can modify data.'

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        if request.method in SAFE_METHODS:
            return True
        return request.user.role in (User.Role.ADMIN, User.Role.MANAGER)


class IsOwnerOrAdmin(BasePermission):
    """Object-level: only the owner or an admin may write."""
    message = 'You do not have permission to modify this resource.'

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        if request.user.role == User.Role.ADMIN:
            return True
        owner = getattr(obj, 'user', None) or getattr(obj, 'owner', None)
        return owner == request.user


class IsProjectMember(BasePermission):
    """Only project members (manager + resources) may access a project."""
    message = 'You are not a member of this project.'

    def has_object_permission(self, request, view, obj):
        user = request.user
        if user.role in (User.Role.ADMIN, User.Role.MANAGER):
            return True
        project = getattr(obj, 'project', obj)
        return (
            project.manager_id == user.pk or
            project.resources.filter(pk=user.pk).exists()
        )
