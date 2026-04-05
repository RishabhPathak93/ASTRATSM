"""accounts/admin.py"""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html
from .models import User, RolePermission


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display    = ['email', 'name', 'role_badge', 'department', 'is_active', 'date_joined', 'last_seen']
    list_filter     = ['role', 'is_active', 'department']
    search_fields   = ['name', 'email', 'department']
    ordering        = ['name']
    readonly_fields = ['date_joined', 'updated_at', 'last_seen', 'initials_display']

    fieldsets = (
        ('Credentials',  {'fields': ('email', 'password')}),
        ('Profile',      {'fields': ('name', 'department', 'phone', 'bio', 'avatar', 'initials_display')}),
        ('Access',       {'fields': ('role', 'is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Timestamps',   {'fields': ('date_joined', 'updated_at', 'last_seen')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'name', 'role', 'department', 'password1', 'password2'),
        }),
    )

    @admin.display(description='Role')
    def role_badge(self, obj):
        colours = {'admin': '#ef4444', 'manager': '#6366f1', 'resource': '#10b981', 'client': '#f59e0b'}
        c = colours.get(obj.role, '#94a3b8')
        return format_html(
            '<span style="background:{};color:white;padding:2px 8px;border-radius:10px;font-size:11px">{}</span>',
            c, obj.get_role_display()
        )

    @admin.display(description='Initials')
    def initials_display(self, obj):
        return obj.initials


@admin.register(RolePermission)
class RolePermissionAdmin(admin.ModelAdmin):
    list_display  = ['role', 'updated_by', 'updated_at']
    readonly_fields = ['updated_by', 'updated_at']

    def has_add_permission(self, request):
        return False  # only created via signal

    def has_delete_permission(self, request, obj=None):
        return False  # permanent rows
