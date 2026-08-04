"""
Kolektor frekuensi REALTIME — ambil nilai terkini dari SYS_FREQ_RT (tabel tanpa
history) dan simpan ke SnapFreqRT untuk membentuk time-series chart dashboard.

    python manage.py collect_freq_rt            # simpan 1 nilai (waktu = sekarang)
    python manage.py collect_freq_rt --dry-run  # tampilkan tanpa menyimpan
    python manage.py collect_freq_rt --probe    # bedah kolom SYS_FREQ_RT

Cron (tiap menit, berbarengan collect_live):
    * * * * * cd /path/to/fasop && venv/bin/python manage.py collect_freq_rt >> /var/log/fasop/collect_freq_rt.log 2>&1

Auto-purge data > RETENSI_HARI (30) hari.
"""
import datetime
from django.core.management.base import BaseCommand
from django.utils import timezone

RETENSI_HARI = 30


class Command(BaseCommand):
    help = 'Ambil frekuensi realtime dari SYS_FREQ_RT → simpan ke SnapFreqRT.'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true')
        parser.add_argument('--probe', action='store_true',
                            help='Tampilkan kolom & contoh baris SYS_FREQ_RT.')
        parser.add_argument('--loop', action='store_true',
                            help='Sampling berulang tiap --interval detik selama --durasi detik.')
        parser.add_argument('--interval', type=float, default=2.0,
                            help='Jeda antar sampel saat --loop (detik, default 2).')
        parser.add_argument('--durasi', type=int, default=60,
                            help='Lama loop (detik, default 60 = satu menit).')

    def handle(self, *args, **opts):
        from opsis import mssql
        from opsis.models import SnapFreqRT

        if opts['probe']:
            info = mssql.probe_freq_rt()
            self.stdout.write(self.style.SUCCESS(
                f"PROBE {info['tabel']}  (kolom nilai dipakai: {info['kolom_dipakai']})"))
            if info.get('error'):
                self.stdout.write(self.style.ERROR(f"  ERROR: {info['error']}"))
            self.stdout.write(f"  Kolom: {info['kolom']}")
            for row in info['contoh']:
                self.stdout.write(f"    {row}")
            self.stdout.write("\nBila kolom Hz bukan 'F', set MSSQL_FREQ_RT_COL di .env.")
            return

        if not mssql.is_reachable():
            self.stdout.write(self.style.ERROR('MSSQL tidak terjangkau — dilewati.'))
            return

        def _simpan(hz):
            """Simpan 1 nilai (waktu floor detik). Return True bila baris baru."""
            waktu = timezone.now().replace(microsecond=0)
            _, created = SnapFreqRT.objects.get_or_create(waktu=waktu, defaults={'hz': hz})
            return created, waktu

        def _purge():
            batas = timezone.now() - datetime.timedelta(days=RETENSI_HARI)
            return SnapFreqRT.objects.filter(waktu__lt=batas).delete()[0]

        # ── Mode LOOP: sampling rapat (mis. tiap 2 dtk) selama --durasi ──
        if opts['loop']:
            import time
            t_akhir = time.monotonic() + opts['durasi']
            n = 0
            while time.monotonic() < t_akhir:
                hz = mssql.get_current_hz()   # persistent connection (efisien saat loop)
                if hz is not None:
                    if opts['dry_run']:
                        self.stdout.write(f'[dry] {timezone.now():%H:%M:%S} = {hz} Hz')
                    else:
                        created, _ = _simpan(hz)
                        n += int(created)
                time.sleep(max(0.2, opts['interval']))
            if not opts['dry_run']:
                hapus = _purge()
                self.stdout.write(self.style.SUCCESS(
                    f'Loop {opts["durasi"]}s @ {opts["interval"]}s: {n} sampel disimpan'
                    + (f'; purge {hapus} lama.' if hapus else '.')))
            return

        # ── Mode sekali (default) ──
        hz = mssql.get_current_hz_rt()
        if hz is None:
            self.stdout.write(self.style.WARNING('Nilai Hz realtime kosong — dilewati.'))
            return
        if opts['dry_run']:
            self.stdout.write(self.style.WARNING(f'[dry-run] {timezone.now():%H:%M:%S} = {hz} Hz'))
            return
        created, waktu = _simpan(hz)
        n_hapus = _purge()
        self.stdout.write(self.style.SUCCESS(
            f'{waktu:%H:%M:%S} = {hz} Hz {"disimpan" if created else "(sudah ada)"}'
            + (f'; purge {n_hapus} lama.' if n_hapus else '.')))
