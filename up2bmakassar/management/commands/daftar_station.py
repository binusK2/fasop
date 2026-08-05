"""
Management command: daftar_station

Daftar station (PATH1) yang muncul di data kinerja, untuk dicocokkan dengan
daftar station milik UP2B. Dipakai untuk memutuskan station mana yang perlu
dinonaktifkan lewat admin (Site (PATH1) Aktif/Tidak) -- misalnya sisa data demo
bawaan Spectrum (Vienna, Paris, PORT, dst) yang ikut masuk ke OFDB.

Membaca PostgreSQL FASOP saja (hasil sync), tidak menyentuh OFDB.

    python manage.py daftar_station
    python manage.py daftar_station --dari 2026-07-01 --sampai 2026-08-04
    python manage.py daftar_station --output station.csv
    python manage.py daftar_station --hanya-aktif
"""
import csv
from datetime import datetime, timedelta

from django.core.management.base import BaseCommand
from django.db.models import Count, Max, Sum
from django.utils import timezone

from up2bmakassar import ofdb
from up2bmakassar.models import KinerjaAnalogHarian, KinerjaDigitalHarian, SitePath1

KOLOM = ['jenis', 'station', 'path1', 'aktif', 'jumlah_titik', 'titik_nol_persen',
         'avail_persen', 'data_terakhir']


class Command(BaseCommand):
    help = 'Daftar station (PATH1) di data kinerja + status aktif/nonaktifnya'

    def add_arguments(self, parser):
        parser.add_argument('--dari', type=str, default=None,
                            help='Tanggal awal (YYYY-MM-DD). Default: 30 hari terakhir.')
        parser.add_argument('--sampai', type=str, default=None,
                            help='Tanggal akhir (YYYY-MM-DD). Default: kemarin.')
        parser.add_argument('--output', type=str, default=None,
                            help='Simpan juga ke file CSV.')
        parser.add_argument('--hanya-aktif', action='store_true',
                            help='Tampilkan hanya station yang berstatus aktif.')

    def _tanggal(self, nilai, default):
        if nilai:
            try:
                return datetime.strptime(nilai, '%Y-%m-%d').date()
            except ValueError:
                pass
        return default

    def handle(self, *args, **options):
        kemarin = timezone.localdate() - timedelta(days=1)
        sampai = self._tanggal(options.get('sampai'), kemarin)
        dari = self._tanggal(options.get('dari'), sampai - timedelta(days=29))

        nonaktif = {
            (v or '').strip()
            for v in SitePath1.objects.filter(aktif=False).values_list('path1', flat=True)
        }

        baris = []
        for model, jenis_list in (
            (KinerjaAnalogHarian, [ofdb.JENIS_TELEMETERING]),
            (KinerjaDigitalHarian, ofdb.JENIS_DIGITAL),
        ):
            for jenis in jenis_list:
                qs = model.objects.filter(jenis=jenis, tanggal__gte=dari, tanggal__lte=sampai)
                for r in qs.values('path1', 'b1').annotate(
                    titik=Count('point_number', distinct=True),
                    uptime=Sum('uptime_detik'),
                    alltime=Sum('alltime_detik'),
                    terakhir=Max('tanggal'),
                ).order_by('path1'):
                    path1 = (r['path1'] or '').strip()
                    aktif = path1 not in nonaktif
                    if options.get('hanya_aktif') and not aktif:
                        continue
                    uptime = float(r['uptime'] or 0)
                    alltime = float(r['alltime'] or 0)
                    nol = qs.filter(path1=r['path1'], uptime_detik=0).values(
                        'point_number').distinct().count()
                    baris.append({
                        'jenis': jenis,
                        'station': (r['b1'] or path1).strip(),
                        'path1': path1,
                        'aktif': 'ya' if aktif else 'tidak',
                        'jumlah_titik': r['titik'],
                        'titik_nol_persen': nol,
                        'avail_persen': round(uptime / alltime * 100, 2) if alltime else 0,
                        'data_terakhir': r['terakhir'],
                    })

        if not baris:
            self.stderr.write(
                f'Tidak ada data kinerja untuk {dari} s/d {sampai}. Jalankan sync dulu.'
            )
            return

        self.stdout.write(f'Station di data kinerja {dari} s/d {sampai}:')
        jenis_sekarang = None
        for b in baris:
            if b['jenis'] != jenis_sekarang:
                jenis_sekarang = b['jenis']
                self.stdout.write(f'\n  {jenis_sekarang}')
                self.stdout.write(
                    f'    {"station":<20}{"aktif":>7}{"titik":>7}{"0%":>6}{"avail":>9}  data terakhir'
                )
            self.stdout.write(
                f'    {b["station"][:20]:<20}{b["aktif"]:>7}{b["jumlah_titik"]:>7}'
                f'{b["titik_nol_persen"]:>6}{b["avail_persen"]:>8.2f}%  {b["data_terakhir"]}'
            )

        total_station = len(baris)
        total_titik = sum(b['jumlah_titik'] for b in baris)
        self.stdout.write(f'\n{total_station} station, {total_titik} titik.')
        self.stdout.write(
            'Station yang bukan milik UP2B (mis. sisa data demo Spectrum) dinonaktifkan '
            'lewat admin: /secure-panel/ -> Up2bmakassar -> Site (PATH1) Aktif/Tidak.'
        )

        if options.get('output'):
            with open(options['output'], 'w', newline='', encoding='utf-8') as f:
                w = csv.DictWriter(f, fieldnames=KOLOM)
                w.writeheader()
                w.writerows(baris)
            self.stdout.write(f'Disimpan juga ke {options["output"]}')
