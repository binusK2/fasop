"""
Management command: sync_kinerja_digital
Hitung kinerja (uptime %) harian titik DIGITAL dari OFDB (dbup2bmakasar.scd_his_digital,
dibaca read-only) dan simpan ke KinerjaDigitalHarian (PostgreSQL).

Titik digital di OFDB terbagi beberapa jenis menurut INDUK point type-nya
(scd_pointtype): TELESIGNAL, RTU, MASTER, TELEKOMUNIKASI. Halaman Telesignal di
app up2bmakassar hanya memakai jenis TELESIGNAL (id_induk_pointtype=21), jadi
default command ini pun TELESIGNAL. Pakai --jenis untuk menghitung jenis lain
(hasilnya masuk tabel yang sama, dibedakan lewat kolom `jenis`).

Default tanggal: kemarin (hari H-1).

Crontab (tiap hari jam 01:00):
    0 1 * * * cd /path/to/fasop && /path/to/venv/bin/python manage.py sync_kinerja_digital >> /var/log/fasop/sync_kinerja_digital.log 2>&1
"""
from datetime import datetime, timedelta

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from up2bmakassar import ofdb
from up2bmakassar.sync import sync_jenis


class Command(BaseCommand):
    help = 'Hitung kinerja harian titik DIGITAL (TELESIGNAL/RTU/MASTER/TELEKOMUNIKASI) dari OFDB'

    def add_arguments(self, parser):
        parser.add_argument('--date', type=str, default=None,
                            help='Tanggal spesifik (YYYY-MM-DD). Default: kemarin.')
        parser.add_argument('--days', type=int, default=1,
                            help='Jumlah hari mundur dari --date/kemarin (untuk backfill). Default 1.')
        parser.add_argument('--jenis', type=str, default=ofdb.JENIS_TELESIGNAL,
                            help='Jenis titik digital: TELESIGNAL (default), RTU, MASTER, '
                                 'TELEKOMUNIKASI, atau ALL untuk semuanya.')
        parser.add_argument('--dry-run', action='store_true',
                            help='Hitung & tampilkan tanpa menyimpan ke database')
        parser.add_argument('--petakan-path', action='store_true',
                            help='Titik kinerja yang point_number-nya sudah mati dicocokkan '
                                 'ulang lewat path1..path5 ke titik yang punya data.')

    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)
        days = max(1, options.get('days') or 1)

        jenis_arg = (options.get('jenis') or ofdb.JENIS_TELESIGNAL).upper()
        if jenis_arg == 'ALL':
            jenis_list = list(ofdb.JENIS_DIGITAL)
        elif jenis_arg in ofdb.JENIS_DIGITAL:
            jenis_list = [jenis_arg]
        else:
            raise CommandError(
                f'--jenis tidak dikenal: {jenis_arg}. Pilihan: {", ".join(ofdb.JENIS_DIGITAL)}, ALL.'
            )

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
            for jenis in jenis_list:
                sync_jenis(cursor, jenis, tanggal_list, dry_run=dry_run,
                           log=self.stdout.write,
                           petakan_path=options.get('petakan_path', False))
        finally:
            conn.close()
