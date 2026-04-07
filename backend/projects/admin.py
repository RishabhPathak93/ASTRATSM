from django.contrib import admin
from .models import Project, ProjectUpdate, ProjectDocument, ProjectApprovalRequest


class ProjectUpdateInline(admin.TabularInline):
    model = ProjectUpdate
    extra = 0
    readonly_fields = ['author', 'created_at']


class ProjectDocumentInline(admin.TabularInline):
    model = ProjectDocument
    extra = 0
    readonly_fields = ['uploaded_by', 'file_size', 'uploaded_at']


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ['name', 'client', 'manager', 'status', 'priority', 'progress', 'end_date', 'budget_utilization']
    list_filter = ['status', 'priority']
    search_fields = ['name', 'description']
    filter_horizontal = ['resources']
    readonly_fields = ['created_by', 'created_at', 'updated_at', 'budget_utilization', 'is_over_budget']
    inlines = [ProjectUpdateInline, ProjectDocumentInline]

    @admin.display(description='Budget Used')
    def budget_utilization(self, obj):
        return f'{obj.budget_utilization}%'


@admin.register(ProjectApprovalRequest)
class ProjectApprovalRequestAdmin(admin.ModelAdmin):
    list_display = ['project', 'request_type', 'status', 'requested_by', 'resolved_by', 'created_at']
    list_filter = ['request_type', 'status', 'created_at']
    search_fields = ['project__name', 'requested_by__name', 'requested_by__email', 'reason']
    readonly_fields = ['created_at', 'resolved_at']
