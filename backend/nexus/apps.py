"""
backend/nexus/apps.py

BUG FIX: previous version's server-detection logic was fragile.
'gunicorn' in sys.modules only works AFTER gunicorn has been imported,
which isn't always the case at AppConfig.ready() time depending on import order.

Fix: use an environment variable ENABLE_SCHEDULER=true that you set explicitly
in your production .env. This is reliable and predictable.

In your backend/.env:
    ENABLE_SCHEDULER=true      ← add this for production / Gunicorn

Leave it unset (or false) during:
    - python manage.py migrate
    - python manage.py collectstatic
    - python manage.py shell  (unless you want to test scheduler manually)
    - pytest / test runs
"""
import os
import sys

from django.apps import AppConfig


class NexusConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'nexus'

    def ready(self):
        # Method 1 (recommended for production): explicit env var
        scheduler_enabled = os.environ.get('ENABLE_SCHEDULER', '').lower() in ('1', 'true', 'yes')

        # Method 2 (fallback for dev): detect runserver
        running_server = 'runserver' in sys.argv

        # Never start in test mode
        in_test = 'test' in sys.argv or 'pytest' in sys.modules

        if (scheduler_enabled or running_server) and not in_test:
            try:
                from nexus import scheduler
                scheduler.start()
            except Exception:
                # Log but don't crash Django startup if scheduler fails
                import logging
                logging.getLogger('nexus').exception(
                    '[scheduler] Failed to start — emails will NOT send automatically. '
                    'Check django_apscheduler is installed and migrations are applied.'
                )