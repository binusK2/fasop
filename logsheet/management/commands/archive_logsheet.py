"""
Arsipkan logsheet harian ke berkas .xlsx (format identik) di folder NAS/lokal.
Dijalankan cron tiap hari 00:05 untuk menyimpan data HARI KEMARIN.

    python manage.py archive_logsheet                       # kemarin -> folder default
    python manage.py archive_logsheet --tanggal 2026-07-27  # tanggal tertentu
    python manage.py archive_logsheet --dir /mnt/nas/logsheet
    python manage.py archive_logsheet --dry-run

Folder tujuan otomatis dibagi per bulan (nama Indonesia), mis:
    <dir>/JULI 2026/LOGSHEET_MKS_20260727.xlsx
Subfolder bulan dibuat otomatis (makedirs) — beda dgn n8n yang tak bisa mkdir.

Default folder diambil dari settings.LOGSHEET_ARCHIVE_DIR (env LOGSHEET_ARCHIVE_DIR),
fallback /mnt/nas/logsheet.
"""
import os
import datetime
from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

BULAN = ['JANUARI', 'FEBRUARI', 'MARET', 'APRIL', 'MEI', 'JUNI', 'JULI',
         'AGUSTUS', 'SEPTEMBER', 'OKTOBER', 'NOVEMBER', 'DESEMBER']


class Command(BaseCommand):
    help = 'Simpan logsheet .xlsx harian ke folder arsip (NAS/lokal), per bulan.'

    def add_arguments(self, parser):
        parser.add_argument('--tanggal', default=None,
                            help='YYYY-MM-DD (default: kemarin).')
        parser.add_argument('--dir', default=None,
                            help='Folder arsip (default: settings.LOGSHEET_ARCHIVE_DIR).')
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **opts):
        from logsheet import export as xls

        if opts['tanggal']:
            try:
                tanggal = datetime.date.fromisoformat(opts['tanggal'])
            except ValueError:
                self.stderr.write(self.style.ERROR('Format --tanggal harus YYYY-MM-DD.'))
                return
        else:
            tanggal = timezone.localdate() - datetime.timedelta(days=1)

        root = (opts['dir']
                or getattr(settings, 'LOGSHEET_ARCHIVE_DIR', '/mnt/nas/logsheet'))
        folder = os.path.join(root, f'{BULAN[tanggal.month - 1]} {tanggal.year}')
        fname = f'LOGSHEET_MKS_{tanggal:%Y%m%d}.xlsx'
        path = os.path.join(folder, fname)

        if opts['dry_run']:
            self.stdout.write(self.style.WARNING(f'[dry-run] akan menulis: {path}'))
            return

        try:
            os.makedirs(folder, exist_ok=True)
        except OSError as e:
            self.stderr.write(self.style.ERROR(f'Gagal buat folder {folder}: {e}'))
            return

        wb = xls.build_workbook(tanggal)
        try:
            wb.save(path)
        except OSError as e:
            self.stderr.write(self.style.ERROR(f'Gagal tulis {path}: {e}'))
            return

        ukuran = os.path.getsize(path)
        self.stdout.write(self.style.SUCCESS(
            f'Arsip tersimpan: {path} ({ukuran // 1024} KB) untuk {tanggal:%Y-%m-%d}.'))
