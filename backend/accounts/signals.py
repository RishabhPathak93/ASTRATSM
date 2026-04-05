"""accounts/signals.py"""
import logging
from django.db.models.signals import post_migrate, post_save
from django.dispatch import receiver

logger = logging.getLogger('nexus')


@receiver(post_migrate)
def create_default_role_permissions(sender, **kwargs):
    """Ensure a RolePermission row exists for every role after each migration."""
    if sender.name != 'accounts':
        return
    from .models import RolePermission, User
    defaults = RolePermission.defaults()
    for role, perms in defaults.items():
        obj, created = RolePermission.objects.get_or_create(
            role=role,
            defaults={'permissions': perms}
        )
        if created:
            logger.info('Created default permissions for role: %s', role)

@receiver(post_save, sender='accounts.User')
def create_resource_profile(sender, instance, created, **kwargs):
    """Auto-create ResourceProfile when a resource user is created."""
    if created and instance.role == 'resource':
        from resources.models import ResourceProfile
        ResourceProfile.objects.get_or_create(user=instance)
