"""
Management command: sync_kinerja_analog
Hitung kinerja (uptime %) harian titik ANALOG / TELEMETERING dari OFDB
(dbup2bmakasar.scd_his_analog, dibaca read-only) dan simpan ke KinerjaAnalogHarian
(PostgreSQL).

Titik yang dihitung = scd_c_point dengan kinerja=1 dan INDUK point type
'TELEMETERING' -- sama persis dengan filter id_induk_pointtype di app
up2bmakassar, bukan sekadar point_type='A'.

Default: hitung untuk kemarin (hari H-1) -- konsisten dengan up2bmakassar lama,
karena hari berjalan datanya belum lengkap sampai lewat tengah malam.

Crontab (tiap hari jam 01:00, setelah tengah malam):
    0 1 * * * cd /path/to/fasop && /path/to/venv/bin/python manage.py sync_kinerja_analog >> /var/log/fasop/sync_kinerja_analog.log 2>&1
"""
from datetime import datetime, timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from up2bmakassar import ofdb
from up2bmakassar.sync import sync_jenis


class Command(BaseCommand):
    help = 'Hitung kinerja harian titik ANALOG (TELEMETERING) dari OFDB -> KinerjaAnalogHarian'

    def add_arguments(self, parser):
        parser.add_argument('--date', type=str, default=None,
                            help='Tanggal spesifik (YYYY-MM-DD). Default: kemarin.')
        parser.add_argument('--days', type=int, default=1,
                            help='Jumlah hari mundur dari --date/kemarin (untuk backfill). Default 1.')
        parser.add_argument('--dry-run', action='store_true',
                            help='Hitung & tampilkan tanpa menyimpan ke database')

    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)
        days = max(1, options.get('days') or 1)

        if options.get('date'):
            anchor = datetime.strptime(options['date'], '%Y-%m-%d').date()
        else:
            anchor = timezone.localdate() - timedelta(days=1)

        tanggal_list = [anchor - timedelta(days=i) for i in range(days)]

        try:
            conn = ofdb.get_connection()
        except Exception as e:
            self.stderr.write(f'[ERROR] Gagal konek OFDB: {e}')
            return

        try:
            sync_jenis(conn.cursor(), ofdb.JENIS_TELEMETERING, tanggal_list,
                       dry_run=dry_run, log=self.stdout.write)
        finally:
            conn.close()
