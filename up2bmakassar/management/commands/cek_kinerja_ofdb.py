"""
Management command: cek_kinerja_ofdb

Diagnosa cepat kenapa halaman Kinerja Scadatel kosong / angkanya beda dengan app
up2bmakassar. Read-only, tidak menulis apa pun (baik ke OFDB maupun PostgreSQL).

Yang dicek:
  1. Koneksi ke OFDB (.env OFDB_*).
  2. Induk point type di scd_pointtype (TELEMETERING/TELESIGNAL/RTU/MASTER/
     TELEKOMUNIKASI) -- kalau namanya beda di OFDB, titiknya tidak ketemu sama
     sekali dan tabel kinerja pasti kosong.
  3. Jumlah titik kinerja=1 per jenis + berapa yang tersaring SitePath1.
  4. Durasi query uptime harian per tabel histori -- kalau lambat (belasan detik
     ke atas), OFDB butuh index di scd_his_analog/scd_his_digital
     (lihat deploy/ofdb_indexes.sql).
  5. Jumlah baris yang sudah tersimpan di PostgreSQL untuk tanggal itu.

    python manage.py cek_kinerja_ofdb [--date YYYY-MM-DD]
"""
import time
from datetime import datetime, timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from up2bmakassar import ofdb
from up2bmakassar.models import KinerjaAnalogHarian, KinerjaDigitalHarian, SitePath1
from up2bmakassar.sync import JENIS_MODEL


class Command(BaseCommand):
    help = 'Diagnosa koneksi & data kinerja SCADATEL di OFDB (read-only)'

    def add_arguments(self, parser):
        parser.add_argument('--date', type=str, default=None,
                            help='Tanggal yang dicek (YYYY-MM-DD). Default: kemarin.')

    def handle(self, *args, **options):
        if options.get('date'):
            tanggal = datetime.strptime(options['date'], '%Y-%m-%d').date()
        else:
            tanggal = timezone.localdate() - timedelta(days=1)

        day_start = datetime.combine(tanggal, datetime.min.time())
        day_end = day_start + timedelta(days=1)

        self.stdout.write(f'Tanggal diperiksa : {tanggal}')

        try:
            conn = ofdb.get_connection()
        except Exception as e:
            self.stderr.write(f'[GAGAL] Koneksi OFDB: {e}')
            self.stderr.write('        Cek OFDB_HOST/OFDB_DB/OFDB_USER/OFDB_PASS di .env.')
            return
        self.stdout.write('[OK]    Koneksi OFDB')

        try:
            cursor = conn.cursor()
            nonaktif = set(SitePath1.objects.filter(aktif=False).values_list('path1', flat=True))

            for jenis in [ofdb.JENIS_TELEMETERING] + list(ofdb.JENIS_DIGITAL):
                induk_id = ofdb.get_induk_pointtype_id(cursor, jenis)
                if induk_id is None:
                    self.stderr.write(
                        f'[GAGAL] Induk point type "{jenis}" tidak ada di scd_pointtype '
                        f'-- tidak ada titik yang bisa dihitung untuk jenis ini.'
                    )
                    continue

                points = ofdb.get_kinerja_points(cursor, jenis)
                aktif = [p for p in points if p['path1'] not in nonaktif]
                station = len({p['path1'] for p in aktif})
                self.stdout.write(
                    f'[OK]    {jenis:<15} id_induk_pointtype={induk_id:<4} '
                    f'titik={len(points):<6} aktif={len(aktif):<6} station={station}'
                )

                semua = ofdb.get_kinerja_points(cursor, jenis, abaikan_point_type=True)
                beda = len(semua) - len(points)
                if beda:
                    point_type, table = ofdb.JENIS_SUMBER[jenis]
                    self.stdout.write(
                        f'        {beda} titik {jenis} punya point_type != "{point_type}" '
                        f'-- histori transisinya bukan di {table}, jadi tidak ikut dihitung.'
                    )

            for table in ofdb.TABEL_HISTORI:
                t0 = time.monotonic()
                hasil = ofdb.compute_kinerja_harian(cursor, table, day_start, day_end)
                lama = time.monotonic() - t0
                catatan = '' if lama < 10 else '  <-- LAMBAT, cek deploy/ofdb_indexes.sql'
                self.stdout.write(
                    f'[OK]    {table:<16} titik dengan transisi VALID={len(hasil):<6} '
                    f'({lama:.1f} detik){catatan}'
                )
        finally:
            conn.close()

        self.stdout.write('--- Tersimpan di PostgreSQL ---')
        for jenis, model in JENIS_MODEL.items():
            jumlah = model.objects.filter(tanggal=tanggal, jenis=jenis).count()
            self.stdout.write(f'        {jenis:<15} {jumlah} baris')

        tanpa_jenis = (KinerjaAnalogHarian.objects.filter(jenis='').count()
                       + KinerjaDigitalHarian.objects.filter(jenis='').count())
        if tanpa_jenis:
            self.stdout.write(
                f'        {tanpa_jenis} baris lama tanpa jenis (hasil versi sebelumnya) -- '
                f'jalankan ulang sync dengan --days untuk menggantinya.'
            )
