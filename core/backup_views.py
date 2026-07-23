import os
import subprocess
import zipfile
import datetime
import logging
from pathlib import Path

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.http import FileResponse, Http404
from django.conf import settings

from .backup_models import BackupSchedule, BackupRecord

logger = logging.getLogger(__name__)


def admin_only(user):
    return user.is_staff or user.is_superuser


def _dump_database(dump_path: Path) -> str:
    """
    Dump the configured database (PostgreSQL or MySQL) to dump_path.
    Returns the archive name to use for the dump inside the backup zip.
    Raises RuntimeError/subprocess.CalledProcessError on failure.
    """
    db_cfg = settings.DATABASES['default']
    engine = db_cfg.get('ENGINE', '')

    if 'postgresql' in engine or 'postgis' in engine:
        env = os.environ.copy()
        if db_cfg.get('PASSWORD'):
            env['PGPASSWORD'] = db_cfg['PASSWORD']

        cmd = [
            'pg_dump',
            '--host', db_cfg.get('HOST', 'localhost'),
            '--port', str(db_cfg.get('PORT', '5432')),
            '--username', db_cfg.get('USER', 'postgres'),
            '--dbname', db_cfg.get('NAME', 'postgres'),
            '--file', str(dump_path),
            '--no-password',
        ]

        result = subprocess.run(
            cmd,
            env=env,
            capture_output=True,
            text=True,
            timeout=300,
        )

        if result.returncode != 0:
            raise RuntimeError(
                f'pg_dump exited with code {result.returncode}. '
                f'stderr: {result.stderr.strip()}'
            )
        return 'database/dump.sql'

    elif 'mysql' in engine:
        env = os.environ.copy()
        if db_cfg.get('PASSWORD'):
            env['MYSQL_PWD'] = db_cfg['PASSWORD']

        cmd = [
            'mysqldump',
            '--host', db_cfg.get('HOST', 'localhost'),
            '--port', str(db_cfg.get('PORT', '3306')),
            '--user', db_cfg.get('USER', 'root'),
            '--result-file', str(dump_path),
            db_cfg.get('NAME', 'ShantiVeer_db'),
        ]

        result = subprocess.run(
            cmd,
            env=env,
            capture_output=True,
            text=True,
            timeout=300,
        )

        if result.returncode != 0:
            raise RuntimeError(
                f'mysqldump exited with code {result.returncode}. '
                f'stderr: {result.stderr.strip()}'
            )
        return 'database/dump.sql'

    else:
        raise RuntimeError(f'Unsupported database engine for backup: {engine}')


def _do_backup(user, backup_type='manual'):
    """
    Core backup logic:
    - Dumps the database (SQLite file copy or MySQL mysqldump)
    - Zips the dump together with the media folder (if it exists)
    - Saves a BackupRecord
    Returns the BackupRecord instance.
    """
    record = BackupRecord.objects.create(
        filename='pending',
        filepath='',
        backup_type=backup_type,
        status='in_progress',
        created_by=user,
    )

    try:
        backup_dir = Path(settings.BASE_DIR) / 'backups'
        backup_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        zip_name = f'hms_backup_{backup_type}_{timestamp}.zip'
        zip_path = backup_dir / zip_name

        # Temporary dump file (inside backup_dir so it's on the same FS)
        dump_path = backup_dir / f'_tmp_dump_{timestamp}'

        try:
            # --- Database dump (SQLite copy or MySQL mysqldump) ---
            arcname_db = _dump_database(dump_path)

            media_path = Path(settings.MEDIA_ROOT) if hasattr(settings, 'MEDIA_ROOT') else None

            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                # Database dump
                zf.write(dump_path, arcname_db)

                # Media files
                if media_path and media_path.exists():
                    for fpath in media_path.rglob('*'):
                        if fpath.is_file():
                            arcname = 'media/' + str(fpath.relative_to(media_path))
                            zf.write(fpath, arcname)

                # Backup manifest
                db_cfg = settings.DATABASES['default']
                engine = db_cfg.get('ENGINE', '')
                if 'mysql' in engine:
                    restore_note = (
                        "To restore:\n"
                        "  mysql --host HOST --port PORT --user USER -p DBNAME < database/dump.sql\n"
                    )
                else:
                    restore_note = (
                        "To restore (PostgreSQL):\n"
                        "  psql --host HOST --port PORT --username USER --dbname DBNAME < database/dump.sql\n"
                    )
                manifest = (
                    f"ShantiVeer HMS Backup\n"
                    f"Type: {backup_type}\n"
                    f"Created: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                    f"User: {user.get_full_name() or user.username if user else 'system'}\n"
                    f"Database: {db_cfg.get('NAME')} @ {db_cfg.get('HOST', 'local file')}\n"
                    f"\n"
                    f"{restore_note}"
                )
                zf.writestr('BACKUP_INFO.txt', manifest)

        finally:
            # Always clean up the temp dump file
            if dump_path.exists():
                dump_path.unlink()

        size = zip_path.stat().st_size
        record.filename = zip_name
        record.filepath = str(zip_path)
        record.size_bytes = size
        record.status = 'success'
        record.save()
        logger.info('Backup created: %s (%d bytes)', zip_name, size)

    except Exception as e:
        record.status = 'failed'
        record.error_message = str(e)
        record.save()
        logger.error('Backup failed: %s', e, exc_info=True)

    return record


@login_required
@user_passes_test(admin_only, login_url='core:dashboard')
def backup_dashboard(request):
    """Main backup management page."""
    schedule = BackupSchedule.objects.first()
    backups = BackupRecord.objects.all()[:20]

    return render(request, 'core/backup.html', {
        'active_sidebar': 'dashboard',
        'schedule': schedule,
        'backups': backups,
    })


@login_required
@user_passes_test(admin_only, login_url='core:dashboard')
def backup_now(request):
    """Trigger an immediate manual backup."""
    if request.method == 'POST':
        record = _do_backup(request.user, backup_type='manual')
        if record.status == 'success':
            messages.success(request, f'Backup created: {record.filename} ({record.size_display})')
        else:
            messages.error(request, f'Backup failed: {record.error_message}')
    return redirect('core:backup')


@login_required
@user_passes_test(admin_only, login_url='core:dashboard')
def backup_schedule_save(request):
    """Save or update the backup schedule preference."""
    if request.method == 'POST':
        frequency = request.POST.get('frequency', 'manual')
        valid = {c[0] for c in BackupSchedule.FREQUENCY_CHOICES}
        if frequency not in valid:
            messages.error(request, 'Invalid frequency selected.')
            return redirect('core:backup')

        is_active = frequency != 'manual'

        schedule, _ = BackupSchedule.objects.get_or_create(pk=1)
        schedule.frequency = frequency
        schedule.is_active = is_active
        schedule.created_by = request.user
        schedule.save()

        label = dict(BackupSchedule.FREQUENCY_CHOICES).get(frequency, frequency)
        messages.success(request, f'Backup schedule set to: {label}')
    return redirect('core:backup')


@login_required
@user_passes_test(admin_only, login_url='core:dashboard')
def backup_download(request, pk):
    """Stream a backup zip file to the browser — path traversal protected."""
    record = get_object_or_404(BackupRecord, pk=pk, status='success')
    path = Path(record.filepath).resolve()
    backup_dir = (Path(settings.BASE_DIR) / 'backups').resolve()

    # Prevent path traversal: ensure file is inside our backup directory
    if not str(path).startswith(str(backup_dir)):
        raise Http404('Invalid backup path.')

    if not path.exists() or not path.is_file():
        raise Http404('Backup file no longer exists on disk.')

    return FileResponse(
        open(path, 'rb'),
        as_attachment=True,
        filename=record.filename,
    )


@login_required
@user_passes_test(admin_only, login_url='core:dashboard')
def backup_delete(request, pk):
    """Delete a backup record and its file."""
    if request.method == 'POST':
        record = get_object_or_404(BackupRecord, pk=pk)
        path = Path(record.filepath).resolve()
        backup_dir = (Path(settings.BASE_DIR) / 'backups').resolve()

        if str(path).startswith(str(backup_dir)) and path.exists():
            path.unlink()
        record.delete()
        messages.success(request, 'Backup deleted.')
    return redirect('core:backup')