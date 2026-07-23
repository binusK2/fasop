"""
Management command: sync_rc
Ambil perintah RC (remote control) dari OFDB (dbup2bmakasar.scd_his_rc, dibaca
read-only), selesaikan hasilnya (BERHASIL/GAGAL) dari scd_his_message kalau OFDB
belum menyelesaikannya sendiri, lalu simpan ke RemoteControl (PostgreSQL).

TIDAK menulis apapun ke OFDB -- resolusi hasil RC dihitung ulang di FASOP karena
job aslinya di up2bmakassar (apps/tasks/jobs/scd_his_rc.py) sudah lama mati.

Default: proses kemarin s/d hari ini (RC yang responnya baru datang setelah
tengah malam tetap ke-cover).

Crontab (tiap 15 menit):
    */15 * * * * cd /path/to/fasop && /path/to/venv/bin/python manage.py sync_rc >> /var/log/fasop/sync_rc.log 2>&1
"""
import logging
from datetime import datetime, timedelta, time

from django.core.management.base import BaseCommand
from django.utils import timezone

from up2bmakassar import ofdb
from up2bmakassar.models import RemoteControl

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Ambil & selesaikan RC dari OFDB scd_his_rc + scd_his_message -> RemoteControl'

    def add_arguments(self, parser):
        parser.add_argument('--date', type=str, default=None,
                             help='Tanggal spesifik (YYYY-MM-DD). Default: kemarin.')
        parser.add_argument('--days', type=int, default=2,
                             help='Jumlah hari mundur dari --date/kemarin (untuk backfill). Default 2.')
        parser.add_argument('--dry-run', action='store_true',
                             help='Hitung & tampilkan tanpa menyimpan ke database')

    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)
        days = max(1, options.get('days') or 2)

        if options.get('date'):
            anchor = datetime.strptime(options['date'], '%Y-%m-%d').date()
        else:
            anchor = timezone.localdate() - timedelta(days=1)

        tanggal_list = sorted(anchor - timedelta(days=i) for i in range(days))

        try:
            conn = ofdb.get_connection()
        except Exception as e:
            self.stderr.write(f'[ERROR] Gagal konek OFDB: {e}')
            return

        try:
            cursor = conn.cursor()

            for tanggal in tanggal_list:
                dt_start = datetime.combine(tanggal, time.min)
                dt_end = datetime.combine(tanggal, time.max)

                events = ofdb.get_rc_events(cursor, dt_start, dt_end)

                diproses = 0
                error = 0

                for row in events:
                    (id_his_rc, path1, path2, path3, path4, path5, b1, b2, b3, elem,
                     datum_1, status_1, datum_2, status_2, operator, cek_remote) = row

                    try:
                        if cek_remote and datum_2 and status_2:
                            # Sudah diselesaikan sendiri oleh OFDB (mis. kasus auto-gagal trigger)
                            hasil_datum, hasil_status = datum_2, status_2
                        else:
                            hasil_datum, _msec, hasil_status = ofdb.resolve_rc_result(
                                cursor, path1, path2, path3, path4, path5, datum_1
                            )

                        if dry_run:
                            self.stdout.write(
                                f'[DRY] {tanggal} id={id_his_rc} {b1}/{b3}/{elem}: {hasil_status}'
                            )
                        else:
                            RemoteControl.objects.update_or_create(
                                ofdb_id_his_rc=id_his_rc,
                                defaults=dict(
                                    path1=path1 or '', path2=path2 or '', path3=path3 or '',
                                    path4=path4 or '', path5=path5 or '',
                                    b1=b1 or '', b2=b2 or '', b3=b3 or '', elem=elem or '',
                                    operator=operator or '', tanggal=tanggal,
                                    datum_eksekusi=datum_1, status_eksekusi=status_1 or '',
                                    datum_respon=hasil_datum, status_respon=hasil_status,
                                ),
                            )
                        diproses += 1
                    except Exception as e:
                        logger.error(f'sync_rc error [id_his_rc={id_his_rc}] {tanggal}: {e}')
                        error += 1

                self.stdout.write(
                    f'[{tanggal}] rc={len(events)} diproses={diproses} error={error}'
                    f'{" (dry-run)" if dry_run else ""}'
                )
        finally:
            conn.close()
