"""
backend/nexus/celery.py

Celery application for AstraTSM.
This file bootstraps Celery and wires up Celery Beat for scheduled tasks.

HOW IT AUTO-RUNS:
  - Celery Worker  processes tasks (sends emails, etc.)
  - Celery Beat    fires the scheduled tasks at the right time (replaces cron)
  Both run as long-lived processes alongside your Django/ASGI server.

STARTUP COMMANDS (run these in separate terminals / supervisor processes):
  # Worker
  celery -A nexus worker --loglevel=info

  # Beat scheduler (NEVER run two beat processes at once)
  celery -A nexus beat --loglevel=info --scheduler django_celery_beat.schedulers:DatabaseScheduler

  OR combined (dev only, not recommended for production):
  celery -A nexus worker --beat --loglevel=info
"""
import os

from celery import Celery
from celery.schedules import crontab

# Tell Django which settings module to use
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'nexus.settings')

app = Celery('nexus')

# Pull CELERY_* settings from Django settings.py
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-discover tasks in all installed apps (looks for tasks.py in each app)
app.autodiscover_tasks()

# ── Scheduled tasks (Celery Beat) ────────────────────────────────────
# These fire automatically — no cron or manual command needed.
# Times are in the timezone set by CELERY_TIMEZONE in settings.py.

app.conf.beat_schedule = {
    # 5:30 PM — first timesheet reminder (weekdays only)
    'timesheet-reminder-1045pm': {
        'task': 'resources.tasks.run_timesheet_reminders',
        'schedule': crontab(hour=10, minute=56, day_of_week='1-5'),  # Mon–Fri
        'kwargs': {'slot': 'first'},
    },
    # 5:45 PM — second timesheet reminder (weekdays only)
    'timesheet-reminder-545pm': {
        'task': 'resources.tasks.run_timesheet_reminders',
        'schedule': crontab(hour=17, minute=45, day_of_week='1-5'),  # Mon–Fri
        'kwargs': {'slot': 'second'},
    },
}