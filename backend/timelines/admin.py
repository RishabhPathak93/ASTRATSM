"""timelines/admin.py"""
from django.contrib import admin
from .models import Timeline, TimelineMilestone


class MilestoneInline(admin.TabularInline):
    model = TimelineMilestone
    extra = 0


@admin.register(Timeline)
class TimelineAdmin(admin.ModelAdmin):
    list_display      = ['name', 'project', 'status', 'progress', 'start_date', 'end_date']
    list_filter       = ['status']
    search_fields     = ['name', 'project__name']
    filter_horizontal = ['assignees']
    readonly_fields   = ['created_at', 'updated_at']
    inlines           = [MilestoneInline]
