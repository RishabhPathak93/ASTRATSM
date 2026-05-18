"""
backend/nexus/scheduler.py

BUG FIX: previous version had the wrong import path for DjangoJobStore.

Wrong:  from apscheduler.jobstores.django_apscheduler.jobstores import DjangoJobStore
Right:  from django_apscheduler.jobstores import DjangoJobStore

The wrong import raises ImportError at startup and the scheduler never starts,
meaning emails are never sent.
"""
import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from django.conf import settings

# BUG FIX: correct import path for DjangoJobStore
from django_apscheduler.jobstores import DjangoJobStore

logger = logging.getLogger('nexus')

_scheduler = None  # module-level singleton — prevents double-start


def _send_slot(slot: str):
    """Wrapper called by APScheduler at scheduled times."""
    try:
        from resources.tasks import send_timesheet_reminders_now
        result = send_timesheet_reminders_now(slot=slot)
        logger.info('[scheduler] Reminder done: %s', result)
    except Exception:
        logger.exception('[scheduler] Reminder FAILED for slot=%s', slot)


def start():
    """
    Start the APScheduler background thread.
    Called once from nexus/apps.py AppConfig.ready().

    After this returns, emails will fire automatically at the scheduled times
    for as long as the Gunicorn/Django process is running.
    """
    global _scheduler
    if _scheduler is not None:
        return  # Already running — guard against double-init in dev reload

    tz = getattr(settings, 'TIME_ZONE', 'UTC')

    _scheduler = BackgroundScheduler(timezone=tz)

    # Store jobs in Django's DB — prevents duplicate fires if you ever
    # run more than one Gunicorn worker.
    _scheduler.add_jobstore(DjangoJobStore(), 'default')

    # ── First reminder: 5:30 PM, Mon–Fri ────────────────────────────
    # To change the time: edit hour and minute here, then restart Gunicorn.
    _scheduler.add_job(
        func=_send_slot,
        kwargs={'slot': 'first'},
        trigger=CronTrigger(
            day_of_week='mon-fri',
            hour=17,
            minute=30,
            timezone=tz,
        ),
        id='timesheet_reminder_first',
        name='Timesheet reminder — 5:30 PM',
        replace_existing=True,   # update if already in DB from a previous run
        misfire_grace_time=300,  # fire up to 5 min late if server was briefly down
    )

    # ── Second reminder: 5:45 PM, Mon–Fri ───────────────────────────
    _scheduler.add_job(
        func=_send_slot,
        kwargs={'slot': 'second'},
        trigger=CronTrigger(
            day_of_week='mon-fri',
            hour=17,
            minute=45,
            timezone=tz,
        ),
        id='timesheet_reminder_second',
        name='Timesheet reminder — 5:45 PM',
        replace_existing=True,
        misfire_grace_time=300,
    )

    _scheduler.start()
    logger.info(
        '[scheduler] Started. Reminders at 17:30 and 17:45 (%s) Mon–Fri.', tz
    )


def shutdown():
    """Stop the scheduler cleanly on server shutdown."""
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        _scheduler = None