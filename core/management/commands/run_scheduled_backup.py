"""
Management command: run_scheduled_backup

Run this DAILY via cron or Windows Task Scheduler.
It checks the active BackupSchedule and creates a backup
only when the schedule frequency triggers.

Setup (Linux cron — runs every day at 2am):
  0 2 * * * cd /path/to/project && /path/to/venv/bin/python manage.py run_scheduled_backup >> /path/to/logs/backup.log 2>&1

Setup (Windows Task Scheduler):
  Program: C:\\path\\to\\venv\\Scripts\\python.exe
  Arguments: C:\\path\\to\\manage.py run_scheduled_backup

Note: No physical backup files are created on the server filesystem beyond
the backups/ directory. The backup is a zip of the DB + media.
"""

import datetime
import logging
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Run a scheduled backup if the configured frequency triggers today.'

    def handle(self, *args, **options):
        from core.backup_models import BackupSchedule
        from core.backup_views import _do_backup

        schedule = BackupSchedule.objects.filter(is_active=True).first()
        if not schedule:
            self.stdout.write('No active backup schedule found. Skipping.')
            return

        today = datetime.date.today()
        frequency = schedule.frequency
        should_run = False

        if frequency == 'daily':
            should_run = True

        elif frequency == 'weekly':
            # Run every Monday (weekday 0)
            should_run = today.weekday() == 0

        elif frequency == 'monthly':
            # Run on the 1st of every month
            should_run = today.day == 1

        elif frequency == 'yearly':
            # Run on Jan 1st
            should_run = today.month == 1 and today.day == 1

        if not should_run:
            self.stdout.write(
                f'Schedule is {frequency} — not due today ({today}). Skipping.'
            )
            return

        admin_user = User.objects.filter(is_superuser=True).first()
        record = _do_backup(admin_user, backup_type=frequency)

        if record.status == 'success':
            msg = f'Backup created: {record.filename} ({record.size_display})'
            self.stdout.write(self.style.SUCCESS(msg))
            logger.info(msg)
        else:
            msg = f'Backup FAILED: {record.error_message}'
            self.stdout.write(self.style.ERROR(msg))
            logger.error(msg)
