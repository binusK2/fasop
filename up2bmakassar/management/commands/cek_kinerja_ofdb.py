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
            if nonaktif:
                self.stdout.write(
                    f'[INFO]  {len(nonaktif)} site (PATH1) dinonaktifkan di admin -- '
                    f'itu hanya menyembunyikan dari halaman, semua titik tetap dihitung.'
                )

            uptime_cache = {}
            for table in ofdb.TABEL_HISTORI:
                t0 = time.monotonic()
                uptime_cache[table] = ofdb.compute_kinerja_harian(cursor, table, day_start, day_end)
                lama = time.monotonic() - t0
                catatan = '' if lama < 10 else '  <-- LAMBAT, cek deploy/ofdb_indexes.sql'
                self.stdout.write(
                    f'[OK]    {table:<16} titik dengan uptime VALID hari itu='
                    f'{len(uptime_cache[table]):<6} ({lama:.1f} detik){catatan}'
                )

            status_cache = {}
            for table in ofdb.TABEL_HISTORI:
                tabel_hari, tabel_rtl = ofdb.TABEL_STATUS[table]
                snap = ofdb.get_status_snapshot(cursor, table, tanggal)
                rtl = ofdb.get_status_realtime(cursor, table)
                his = ofdb.get_status_sebelum(cursor, table, day_start)
                status_cache[table] = ofdb.get_status_awal_hari(cursor, table, tanggal, day_start, rtl)
                self.stdout.write(
                    f'[OK]    status awal hari {table:<16} '
                    f'{tabel_hari}={len(snap)} transisi_sebelumnya={len(his)} {tabel_rtl}={len(rtl)}'
                )

            for jenis in [ofdb.JENIS_TELEMETERING] + list(ofdb.JENIS_DIGITAL):
                induk_id = ofdb.get_induk_pointtype_id(cursor, jenis)
                if induk_id is None:
                    self.stdout.write(
                        f'[SKIP]  Induk point type "{jenis}" tidak ada di scd_pointtype '
                        f'-- jenis ini memang tidak dipakai di OFDB ini.'
                    )
                    continue

                point_type, table = ofdb.JENIS_SUMBER[jenis]
                points = ofdb.get_kinerja_points(cursor, jenis)
                if not points:
                    self.stdout.write(
                        f'[INFO]  {jenis:<15} id_induk_pointtype={induk_id} -- '
                        f'tidak ada titik dengan kinerja=1.'
                    )
                    continue

                uptime_map = uptime_cache[table]
                status = status_cache[table]
                nomor = [p['point_number'] for p in points]
                punya_uptime = sum(1 for n in nomor if n in uptime_map)
                punya_status = sum(1 for n in nomor
                                   if n not in uptime_map and status.get(n) == 'VALID')
                nihil = len(nomor) - punya_uptime - punya_status
                station = len({p['path1'] for p in points})
                tampil = len({p['path1'] for p in points if p['path1'] not in nonaktif})

                self.stdout.write(
                    f'[OK]    {jenis:<15} id_induk_pointtype={induk_id:<4} titik={len(points):<6} '
                    f'station={station} (tampil={tampil})'
                )
                self.stdout.write(
                    f'          -> ada uptime hari itu={punya_uptime}, '
                    f'ditolong status awal hari={punya_status}, tanpa data={nihil}'
                )
                if nihil:
                    contoh = [str(n) for n in nomor if n not in uptime_map
                              and status.get(n) != 'VALID'][:8]
                    self.stdout.write(
                        f'          -> contoh point_number tanpa data: {", ".join(contoh)}'
                    )

                semua = ofdb.get_kinerja_points(cursor, jenis, abaikan_point_type=True)
                beda = len(semua) - len(points)
                if beda:
                    self.stdout.write(
                        f'          -> {beda} titik {jenis} punya point_type != "{point_type}", '
                        f'histori transisinya bukan di {table} sehingga tidak ikut dihitung.'
                    )

            # Contoh nilai duluan -- blok ini paling murah dan paling sering
            # menjelaskan masalahnya (beda tipe data / beda ruang penomoran).
            self.stdout.write('--- Contoh point_number apa adanya (cek tipe data) ---')
            for table in ('scd_c_point', 'scd_his_analog', 'scd_analog_rtl',
                          'scd_his_digital', 'scd_digital_rtl'):
                try:
                    if table == 'scd_c_point':
                        cursor.execute('SELECT DISTINCT TOP 5 point_number FROM scd_c_point '
                                       'WHERE kinerja = 1 ORDER BY point_number')
                        contoh = [row[0] for row in cursor.fetchall()]
                    else:
                        contoh = ofdb.contoh_point_number(cursor, table)
                except Exception as e:
                    self.stdout.write(f'    {table:<18} tidak terbaca ({e})')
                    continue
                tipe = type(contoh[0]).__name__ if contoh else '-'
                self.stdout.write(f'    {table:<18} {tipe:<8} {contoh}')

            # ── Cakupan point_number: dicek di sisi SQL Server ──────────────────
            # Menjawab pertanyaan "apakah point_number titik kinerja memang ada di
            # tabel histori/realtime?" tanpa dipengaruhi tipe data di Python.
            self.stdout.write('--- Cakupan point_number (EXISTS di sisi OFDB) ---')
            for point_type in ('A', 'D'):
                table = 'scd_his_analog' if point_type == 'A' else 'scd_his_digital'
                _, tabel_rtl = ofdb.TABEL_STATUS[table]
                self.stdout.write(f'  point_type={point_type}  ({table} / {tabel_rtl})')
                try:
                    baris = ofdb.ringkasan_cakupan(cursor, point_type)
                except Exception as e:
                    self.stderr.write(f'    gagal: {e}')
                    continue
                self.stdout.write(
                    f'    {"jenis":<18}{"kinerja":>8}{"titik":>8}{"ada_histori":>13}{"ada_rtl":>9}'
                )
                for jenis, kinerja, titik, ada_his, ada_rtl in baris:
                    self.stdout.write(
                        f'    {(jenis or "-"):<18}{kinerja if kinerja is not None else "-":>8}'
                        f'{titik:>8}{ada_his:>13}{ada_rtl:>9}'
                    )

            # ── Bisakah titik mati diselamatkan lewat path? ─────────────────────
            # Identitas logis titik = path1..path5 (B1/B2/B3/Element/Info).
            # Kalau titik kinerja=1 menunjuk point_number mati tapi ada titik lain
            # dengan path sama persis yang punya data, sync --petakan-path bisa
            # memakai titik itu tanpa perlu mengubah apa pun di OFDB.
            self.stdout.write('--- Uji pemetaan lewat path1..path5 ---')
            for jenis in [ofdb.JENIS_TELEMETERING, ofdb.JENIS_TELESIGNAL]:
                try:
                    points = ofdb.get_kinerja_points(cursor, jenis)
                    if not points:
                        continue
                    point_type, table = ofdb.JENIS_SUMBER[jenis]
                    berdata = ofdb.get_point_berdata(cursor, table)
                    semua = ofdb.get_point_paths(cursor, point_type)
                    contoh = [p for p in points if p['point_number'] not in berdata][:3]
                    asal = {id(p): p['point_number'] for p in contoh}
                    dipetakan, gagal = ofdb.cari_kembaran(points, semua, berdata)
                except Exception as e:
                    self.stderr.write(f'    {jenis}: gagal ({e})')
                    continue

                self.stdout.write(
                    f'    {jenis:<15} bisa dipetakan={dipetakan}, tidak ketemu kembarannya={gagal}'
                )
                for p in contoh:
                    if 'point_number_asal' in p:
                        self.stdout.write(
                            f'          {asal[id(p)]} -> {p["point_number"]}  '
                            f'({p["b1"]}/{p["b2"]}/{p["b3"]}/{p["elem"]})'
                        )
                if dipetakan:
                    self.stdout.write(
                        f'          jalankan sync dengan --petakan-path untuk memakai pemetaan ini.'
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
