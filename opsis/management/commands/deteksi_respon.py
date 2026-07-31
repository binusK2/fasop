"""
Deteksi event frekuensi & buat PDF Respons Pembangkit — meniru Excel Respons Kit.

Dijalankan cron (mis. tiap menit). Memindai frekuensi sistem N menit terakhir
dari SYS_FREQ_HIS; bila deviasi dari 50 Hz melewati ambang (default 0.2 =
Siaga), rakit analisis respons semua pembangkit dari HIS_MEAS_KIT (lookback),
buat PDF, dan simpan ke folder NAS per kategori:

    <RESPON_ARCHIVE_DIR>/<Aman|Siaga|Bahaya>/Respons Kit Sulbagsel <YYYYMMDD HHMMSS>.pdf

Contoh cron (tiap menit):
    * * * * * cd /home/fasop/fasop && venv/bin/python manage.py deteksi_respon >> /home/fasop/respon.log 2>&1

Opsi:
    --menit N     jendela pindai ke belakang (default 2)
    --ambang X    deviasi minimal Hz agar dianggap event (default 0.2)
    --sebelum S   detik sebelum titik ekstrem untuk baseline (default 60)
    --sesudah S   detik sesudah titik ekstrem (default 180)
    --pusat "YYYY-MM-DD HH:MM:SS"  paksa buat PDF untuk waktu ini (manual/backfill)
    --dry-run     hanya tampilkan, tidak menulis PDF
"""
import os
import glob
import datetime
from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone


class Command(BaseCommand):
    help = 'Deteksi event frekuensi & simpan PDF Respons Pembangkit ke NAS per kategori.'

    def add_arguments(self, parser):
        parser.add_argument('--menit', type=int, default=2)
        parser.add_argument('--ambang', type=float, default=None)
        parser.add_argument('--sebelum', type=int, default=60)
        parser.add_argument('--sesudah', type=int, default=180)
        parser.add_argument('--pusat', default=None)
        parser.add_argument('--probe', default=None,
                            help='Bedah data mentah 1 KIT (kode) untuk jendela --pusat±.')
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **o):
        from opsis import mssql, respon as R, respon_pdf as P
        from opsis.models import Pembangkit

        ambang = o['ambang'] if o['ambang'] is not None else R.AMBANG_SIAGA
        root   = getattr(settings, 'RESPON_ARCHIVE_DIR', '/mnt/nas/respon_kit')
        judul  = getattr(settings, 'RESPON_JUDUL', 'Respons Pembangkit Sistem Sulbagsel')

        # ── Mode probe: bedah data mentah HIS_MEAS_KIT untuk satu KIT ──
        if o['probe']:
            pusat = (datetime.datetime.strptime(o['pusat'], '%Y-%m-%d %H:%M:%S')
                     if o['pusat'] else datetime.datetime.now())
            t0 = pusat - datetime.timedelta(seconds=o['sebelum'])
            t1 = pusat + datetime.timedelta(seconds=o['sesudah'])
            info = mssql.probe_kit(o['probe'], t0, t1)
            self.stdout.write(self.style.SUCCESS(
                f"PROBE {o['probe']}  [{t0} .. {t1}]"))
            self.stdout.write(f"  Unit (B3): {info['units']}")
            self.stdout.write(f"  Jumlah baris: {info['jumlah_baris']}  "
                              f"Resolusi ≈ {info['resolusi_detik']} detik/sampel")
            self.stdout.write("  Contoh (TIME, B3, P):")
            for row in info['contoh'][:20]:
                self.stdout.write(f"    {row}")
            return

        plist = [(p.nama, (p.kode_kit or p.kode))
                 for p in Pembangkit.objects.filter(aktif=True)]
        get_freq = mssql.get_freq_range
        get_mw   = lambda a, b: mssql.get_kit_unit_mw_range(plist, a, b)   # PER-UNIT

        # ── tentukan titik-titik event ──
        if o['pusat']:
            try:
                pusat = datetime.datetime.strptime(o['pusat'], '%Y-%m-%d %H:%M:%S')
            except ValueError:
                self.stderr.write(self.style.ERROR("Format --pusat: 'YYYY-MM-DD HH:MM:SS'"))
                return
            titik = [pusat]
        else:
            if not mssql.is_reachable():
                self.stdout.write(self.style.ERROR('MSSQL tidak terjangkau — dilewati.'))
                return
            now = timezone.localtime().replace(tzinfo=None)
            seq = get_freq(now - datetime.timedelta(minutes=o['menit']), now)
            events = R.deteksi_events(seq, ambang=ambang)
            titik = [e['t_ekstrem'] for e in events]
            if not titik:
                self.stdout.write(f'Tidak ada event (ambang {ambang} Hz) '
                                  f'dalam {o["menit"]} menit terakhir.')
                return

        n_pdf = 0
        for pusat in titik:
            a = R.analisa_event(pusat, get_freq, get_mw,
                                o['sebelum'], o['sesudah'])
            if a['df'] is None:
                self.stdout.write(f'  {pusat}: tak ada data frekuensi — dilewati.')
                continue
            kat = a['kategori']
            folder = os.path.join(root, kat)
            fname = f'Respons Kit Sulbagsel {pusat:%Y%m%d %H%M%S}.pdf'
            path = os.path.join(folder, fname)

            if self._sudah_ada(root, pusat):
                self.stdout.write(f'  {pusat:%H:%M:%S} {kat} (Δf={a["df"]}) — sudah ada, lewati.')
                continue

            if o['dry_run']:
                self.stdout.write(self.style.WARNING(
                    f'  [dry-run] {kat} Δf={a["df"]} -> {path}'))
                n_pdf += 1
                continue

            try:
                os.makedirs(folder, exist_ok=True)
                pdf = P.build_pdf(a, judul)
                with open(path, 'wb') as f:
                    f.write(pdf)
            except Exception as e:
                self.stderr.write(self.style.ERROR(f'  Gagal tulis {path}: {e}'))
                continue
            n_pdf += 1
            self.stdout.write(self.style.SUCCESS(
                f'  {kat}  Δf={a["df"]} Hz  ->  {path} ({len(pdf)//1024} KB)'))

        self.stdout.write(self.style.SUCCESS(
            (self.style.WARNING('[dry-run] ') if o['dry_run'] else '') +
            f'{n_pdf} PDF respons dibuat.'))

    def _sudah_ada(self, root, pusat, jeda_detik=300):
        """True bila sudah ada PDF untuk event dalam ±jeda_detik (anti-dobel
        saat jendela cron bergeser lintas run)."""
        for path in glob.glob(os.path.join(root, '*', 'Respons Kit Sulbagsel *.pdf')):
            base = os.path.basename(path)
            stamp = base.replace('Respons Kit Sulbagsel ', '').replace('.pdf', '')
            try:
                t = datetime.datetime.strptime(stamp, '%Y%m%d %H%M%S')
            except ValueError:
                continue
            if abs((t - pusat).total_seconds()) <= jeda_detik:
                return True
        return False
