"""notifications/utils.py"""
import logging
from accounts.models import User

logger = logging.getLogger('nexus')


def _should_notify(user, notif_type: str) -> bool:
    """
    Admin & Manager  → always notify.
    Resource         → check their NotificationPreference (default: all allowed).
    """
    if user.role in (User.Role.ADMIN, User.Role.MANAGER):
        return True
    if user.role == User.Role.RESOURCE:
        from .models import ResourceNotificationPreference, ALL_NOTIF_TYPES
        allowed = ResourceNotificationPreference.get_allowed(user)
        return notif_type in allowed
    return False


def _bulk_notify(users, notif_type, title, message,
                 project=None, action_url='') -> int:
    from .models import Notification
    to_create = [
        Notification(
            user=u, notif_type=notif_type, title=title,
            message=message, project=project, action_url=action_url,
        )
        for u in users
        if u and u.is_active and _should_notify(u, notif_type)
    ]
    if to_create:
        Notification.objects.bulk_create(to_create, ignore_conflicts=True)
    logger.debug('Created %d notifications [%s]: %s', len(to_create), notif_type, title)
    return len(to_create)


# ── Public API ────────────────────────────────────────────────────────────────

def notify_project_team(users, notif_type, title, message,
                        project=None, action_url='', exclude=None):
    filtered = [u for u in users if u != exclude]
    return _bulk_notify(filtered, notif_type, title, message, project, action_url)


def notify_user(user, notif_type, title, message, project=None, action_url=''):
    return _bulk_notify([user], notif_type, title, message, project, action_url)


def notify_admins_and_managers(notif_type, title, message,
                               project=None, action_url='', exclude=None):
    recipients = list(User.objects.filter(
        role__in=[User.Role.ADMIN, User.Role.MANAGER],
        is_active=True,
    ))
    if exclude:
        recipients = [u for u in recipients if u != exclude]
    return _bulk_notify(recipients, notif_type, title, message, project, action_url)