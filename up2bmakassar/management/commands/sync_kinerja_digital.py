"""
Management command: sync_kinerja_digital
Hitung kinerja (uptime %) harian titik DIGITAL dari OFDB (dbup2bmakasar.scd_his_digital,
dibaca read-only) dan simpan ke KinerjaDigitalHarian (PostgreSQL).

Default: hitung untuk kemarin (hari H-1).

Crontab (tiap hari jam 01:00):
    0 1 * * * cd /path/to/fasop && /path/to/venv/bin/python manage.py sync_kinerja_digital >> /var/log/fasop/sync_kinerja_digital.log 2>&1
"""
import logging
from datetime import datetime, timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from up2bmakassar import ofdb
from up2bmakassar.models import KinerjaDigitalHarian, SitePath1

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Hitung kinerja harian titik DIGITAL dari OFDB -> KinerjaDigitalHarian'

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
            cursor = conn.cursor()

            # Seed SitePath1 dengan path1 baru yang belum pernah terlihat (default aktif=True)
            for path1 in ofdb.get_all_kinerja_path1(cursor, point_type='D'):
                SitePath1.objects.get_or_create(path1=path1)

            active_path1 = list(SitePath1.objects.filter(aktif=True).values_list('path1', flat=True))
            points = ofdb.get_kinerja_points(cursor, point_type='D', active_path1=active_path1)

            if not points:
                self.stdout.write('Tidak ada titik DIGITAL dengan kinerja=1 di scd_c_point.')
                return

            for tanggal in sorted(tanggal_list):
                day_start = datetime.combine(tanggal, datetime.min.time())
                day_end = day_start + timedelta(days=1)

                dihitung = 0
                error = 0

                for point_number, path1, path2, path3 in points:
                    try:
                        jlh, uptime, performance = ofdb.compute_point_kinerja(
                            cursor, 'scd_his_digital', point_number, day_start, day_end
                        )

                        if dry_run:
                            self.stdout.write(
                                f'[DRY] {tanggal} point={point_number}: '
                                f'up={jlh} uptime={uptime:.0f}s performance={performance:.2f}%'
                            )
                        else:
                            KinerjaDigitalHarian.objects.update_or_create(
                                point_number=point_number,
                                tanggal=tanggal,
                                defaults=dict(
                                    path1=path1 or '', path2=path2 or '', path3=path3 or '',
                                    jumlah_up=jlh,
                                    uptime_detik=uptime,
                                    alltime_detik=(day_end - day_start).total_seconds(),
                                    performance=performance,
                                ),
                            )
                        dihitung += 1
                    except Exception as e:
                        logger.error(f'sync_kinerja_digital error [{point_number}] {tanggal}: {e}')
                        error += 1

                self.stdout.write(
                    f'[{tanggal}] titik={len(points)} dihitung={dihitung} error={error}'
                    f'{" (dry-run)" if dry_run else ""}'
                )
        finally:
            conn.close()
