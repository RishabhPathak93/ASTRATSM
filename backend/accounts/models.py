"""accounts/models.py"""
import logging
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.core.validators import RegexValidator
from django.db import models
from django.utils import timezone

logger = logging.getLogger('nexus')

phone_validator = RegexValidator(
    regex=r'^\+?1?\d{9,15}$',
    message='Phone number must be entered in the format: +999999999. Up to 15 digits.'
)


class UserManager(BaseUserManager):
    def create_user(self, email: str, password: str, **extra_fields):
        if not email:
            raise ValueError('Email address is required.')
        if not password:
            raise ValueError('Password is required.')
        email = self.normalize_email(email.strip().lower())
        extra_fields.setdefault('is_active', True)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.full_clean()           # run model-level validation
        user.save(using=self._db)
        logger.info('Created user %s (%s)', user.email, user.role)
        return user

    def create_superuser(self, email: str, password: str, **extra_fields):
        extra_fields.setdefault('role', User.Role.ADMIN)
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')
        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    class Role(models.TextChoices):
        ADMIN    = 'admin',    'Admin'
        MANAGER  = 'manager',  'Project Manager'
        RESOURCE = 'resource', 'Resource'
        CLIENT   = 'client',   'Client'

    email      = models.EmailField(unique=True, db_index=True)
    name       = models.CharField(max_length=150)
    role       = models.CharField(max_length=20, choices=Role.choices, default=Role.RESOURCE, db_index=True)
    department = models.CharField(max_length=100, blank=True)
    phone      = models.CharField(max_length=20, blank=True, validators=[phone_validator])
    bio        = models.TextField(blank=True, max_length=500)
    avatar     = models.ImageField(upload_to='avatars/%Y/%m/', null=True, blank=True)

    is_active  = models.BooleanField(default=True, db_index=True)
    is_staff   = models.BooleanField(default=False)

    date_joined = models.DateTimeField(default=timezone.now)
    updated_at  = models.DateTimeField(auto_now=True)
    last_seen   = models.DateTimeField(null=True, blank=True)

    objects = UserManager()

    USERNAME_FIELD  = 'email'
    REQUIRED_FIELDS = ['name']

    class Meta:
        ordering     = ['name']
        verbose_name = 'User'
        indexes      = [models.Index(fields=['email', 'role'])]

    def __str__(self):
        return f'{self.name} <{self.email}>'

    def clean(self):
        from django.core.exceptions import ValidationError
        self.email = self.email.strip().lower()
        self.name  = self.name.strip()
        if not self.name:
            raise ValidationError({'name': 'Name cannot be blank.'})

    @property
    def initials(self) -> str:
        parts = self.name.split()
        return ''.join(p[0].upper() for p in parts[:2])

    def touch(self):
        """Update last_seen without triggering updated_at via auto_now."""
        User.objects.filter(pk=self.pk).update(last_seen=timezone.now())


class RolePermission(models.Model):
    """
    Per-role permission matrix, editable at runtime by admins/managers.
    Schema: {page_key: bool}  e.g. {"dashboard": true, "clients": false}
    """
    role        = models.CharField(max_length=20, choices=User.Role.choices, unique=True)
    permissions = models.JSONField(default=dict)
    updated_by  = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='+', limit_choices_to={'role__in': ['admin', 'manager']}
    )
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Role Permission'

    def __str__(self):
        return f'Permissions [{self.role}]'

    @classmethod
    def defaults(cls):
        return {
            User.Role.ADMIN:    {'dashboard':True,'clients':True,'projects':True,'timelines':True,'resources':True,'chat':True,'reports':True,'access_control':True},
            User.Role.MANAGER:  {'dashboard':True,'clients':True,'projects':True,'timelines':True,'resources':True,'chat':True,'reports':True,'access_control':False},
            User.Role.RESOURCE: {'dashboard':True,'clients':False,'projects_view':True,'timelines_view':True,'chat':True,'reports':False,'access_control':False},
            User.Role.CLIENT:   {'dashboard':True,'projects_view':True,'timelines_view':True,'chat':False,'reports':False,'access_control':False},
        }

    @classmethod
    def get_for_role(cls, role: str) -> dict:
        try:
            return cls.objects.get(role=role).permissions
        except cls.DoesNotExist:
            return cls.defaults().get(role, {})
