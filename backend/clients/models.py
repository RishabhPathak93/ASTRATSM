"""clients/models.py"""
from django.db import models
from django.core.validators import URLValidator
from accounts.models import User


class Client(models.Model):
    class Status(models.TextChoices):
        ACTIVE   = 'active',   'Active'
        INACTIVE = 'inactive', 'Inactive'

    name             = models.CharField(max_length=200)
    email            = models.EmailField(db_index=True)
    email2           = models.EmailField(blank=True)
    phone            = models.CharField(max_length=30, blank=True)
    phone2           = models.CharField(max_length=30, blank=True)
    industry         = models.CharField(max_length=100, blank=True, db_index=True)
    address          = models.TextField(blank=True)
    contact_person   = models.CharField(max_length=150, blank=True)
    contact_person2  = models.CharField(max_length=150, blank=True)
    website          = models.URLField(blank=True, validators=[URLValidator()])
    notes            = models.TextField(blank=True)
    status           = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE, db_index=True)
    logo           = models.ImageField(upload_to='clients/logos/%Y/%m/', null=True, blank=True)

    onboarded_by   = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='onboarded_clients')
    onboarded_at   = models.DateTimeField(auto_now_add=True)
    updated_at     = models.DateTimeField(auto_now=True)

    # Optional linked portal account
    portal_user    = models.OneToOneField(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='client_profile',
        limit_choices_to={'role': 'client'},
    )

    class Meta:
        ordering = ['name']
        indexes  = [models.Index(fields=['status', 'industry'])]

    def __str__(self):
        return self.name


class ClientContact(models.Model):
    client     = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='contacts')
    name       = models.CharField(max_length=150)
    email      = models.EmailField()
    phone      = models.CharField(max_length=30, blank=True)
    position   = models.CharField(max_length=100, blank=True)
    is_primary = models.BooleanField(default=False)

    class Meta:
        ordering     = ['-is_primary', 'name']
        constraints  = [
            models.UniqueConstraint(
                fields=['client'], condition=models.Q(is_primary=True),
                name='unique_primary_contact_per_client'
            )
        ]

    def __str__(self):
        return f'{self.name} @ {self.client.name}'