"""
backend/nexus/__init__.py

Import the Celery app here so it is loaded whenever Django starts.
This is required for @shared_task decorators to work correctly.
"""
from .celery import app as celery_app

__all__ = ('celery_app',)