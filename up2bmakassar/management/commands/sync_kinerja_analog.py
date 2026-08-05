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
        parser.add_argument('--titik', type=str, default=ofdb.SUMBER_KINERJA,
                            choices=[ofdb.SUMBER_KINERJA, ofdb.SUMBER_BERDATA],
                            help='Daftar titik diambil dari mana: "kinerja" (flag kinerja=1 di '
                                 'scd_c_point, cara app up2bmakassar) atau "berdata" (semua titik '
                                 'jenis ini yang punya baris di tabel realtime OFDB).')
        parser.add_argument('--sertakan-tanpa-data', action='store_true',
                            help='Ikut simpan titik yang tidak punya jejak apa pun di OFDB '
                                 'sebagai 0%% (default: dilewati, karena statusnya tidak '
                                 'diketahui dan bikin rata-rata availability ngawur).')
        parser.add_argument('--petakan-path', action='store_true',
                            help='Titik kinerja yang point_number-nya sudah mati dicocokkan '
                                 'ulang lewat path1..path5 ke titik yang punya data.')

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
                       dry_run=dry_run, log=self.stdout.write,
                       petakan_path=options.get('petakan_path', False),
                       sumber=options.get('titik') or ofdb.SUMBER_KINERJA,
                       sertakan_tanpa_data=options.get('sertakan_tanpa_data', False))
        finally:
            conn.close()
