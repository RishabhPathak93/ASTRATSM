"""clients/admin.py"""
from django.contrib import admin
from .models import Client, ClientContact


class ClientContactInline(admin.TabularInline):
    model = ClientContact
    extra = 0


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display  = ['name', 'email', 'industry', 'status', 'contact_person', 'onboarded_at']
    list_filter   = ['status', 'industry']
    search_fields = ['name', 'email', 'contact_person']
    readonly_fields = ['onboarded_by', 'onboarded_at', 'updated_at']
    inlines       = [ClientContactInline]
