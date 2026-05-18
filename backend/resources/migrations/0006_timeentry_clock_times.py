"""
Migration: add slot_label field to TimesheetReminderLog

Add this as resources/migrations/0006_timesheetreminderlog_slot_label.py
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('resources', '0005_timesheetreminderlog_timesheetlateentryapproval_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='timesheetreminderlog',
            name='slot_label',
            field=models.CharField(
                max_length=16,
                default='first',
                choices=[('first', '17:30 Reminder'), ('second', '17:45 Reminder')],
                help_text='Which scheduled reminder slot fired this log entry.',
            ),
        ),
    ]