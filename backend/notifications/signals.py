"""
backend/notifications/signals.py

BUG FIX: previous version called build_no_reply_email() and
send_notification_email() directly — but the correct internal API is
email_no_reply() from notifications.utils, which handles deduplication,
active-user checks, HTML building, and sending all in one place.

Wire up in notifications/apps.py:
    def ready(self):
        import notifications.signals  # noqa: F401
"""
import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

logger = logging.getLogger('nexus')


@receiver(post_save, sender='notifications.Notification')
def on_notification_created(sender, instance, created, **kwargs):
    """
    Email the recipient whenever a new unread notification is created.
    Does NOT re-email when the notification is later marked as read.
    """
    if not created:
        return

    if getattr(instance, 'is_read', False):
        return

    user = instance.user
    if not user or not user.is_active:
        return

    try:
        from notifications.utils import email_no_reply

        email_no_reply(
            [user],
            subject='You have a new notification in AstraTSM',
            heading=f'Hi {user.get_full_name() or user.username},',
            intro=(
                'You have received a new notification in AstraTSM. '
                'If you have already seen it in the app, please ignore this email.'
            ),
            details=[
                ('Type', getattr(instance, 'notif_type', '')),
                ('Title', instance.title or ''),
                ('Message', instance.message or ''),
            ] + (
                [('Link', instance.action_url)]
                if getattr(instance, 'action_url', None)
                else []
            ),
            footer_note=(
                'This is an automated no-reply message from AstraTSM. '
                'You received this because a notification was created for your account.'
            ),
        )
        logger.debug(
            '[notification-signal] Email sent to user_id=%s notif_id=%s',
            user.id, instance.pk,
        )
    except Exception:
        logger.warning(
            '[notification-signal] Failed to email user_id=%s notif_id=%s',
            getattr(user, 'id', '?'), instance.pk,
            exc_info=True,
        )