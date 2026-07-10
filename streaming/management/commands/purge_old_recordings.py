"""
Management command: purge_old_recordings
Hapus file rekaman live streaming yang sudah lewat masa retensi
(STREAMING_RECORDING_RETENTION_DAYS, default 7 hari) dihitung sejak
sesi live diakhiri (ended_at).

Crontab (harian, mis. jam 03:00):
    0 3 * * * cd /path/to/fasop && /path/to/venv/bin/python manage.py purge_old_recordings >> /var/log/fasop/purge_old_recordings.log 2>&1
"""
import logging
import os

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from streaming.models import LiveSession

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Hapus file rekaman live streaming yang sudah lewat masa retensi'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true',
                             help='Tampilkan yang akan dihapus tanpa benar-benar menghapus')

    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)
        retensi_hari = settings.STREAMING_RECORDING_RETENTION_DAYS
        batas = timezone.now() - timezone.timedelta(days=retensi_hari)

        sessions = LiveSession.objects.filter(
            status='ended',
            ended_at__lt=batas,
        ).exclude(recording_path='')

        total = 0
        for session in sessions:
            path = session.recording_path
            if dry_run:
                self.stdout.write(f'[DRY-RUN] Akan dihapus: {path} (sesi #{session.pk}, berakhir {session.ended_at})')
            else:
                try:
                    if os.path.isfile(path):
                        os.remove(path)
                except OSError as e:
                    logger.warning('Gagal hapus file rekaman %s: %s', path, e)
                session.recording_path = ''
                session.save(update_fields=['recording_path'])
            total += 1

        if dry_run:
            self.stdout.write(self.style.SUCCESS(f'[DRY-RUN] {total} rekaman lewat retensi {retensi_hari} hari.'))
        else:
            self.stdout.write(self.style.SUCCESS(f'{total} rekaman dihapus (lewat retensi {retensi_hari} hari).'))
