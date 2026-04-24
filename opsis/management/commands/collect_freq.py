"""
Management command: collect_freq
Ambil data frekuensi per detik dari SYS_FREQ_HIS → simpan ke PostgreSQL (SnapFreq).
Auto-purge: hapus data lebih dari 30 hari secara otomatis.

Jadwal via crontab (setiap menit, berbarengan dengan collect_live):
    * * * * * cd /path/to/fasop && /home/fasop/fasop/venv/bin/python manage.py collect_freq >> /var/log/fasop/collect_freq.log 2>&1

Estimasi storage: 86.400 baris/hari × 30 hari ≈ 2.6 juta baris (~130 MB).
"""
import logging
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import IntegrityError
from opsis.models import SnapFreq
from opsis import mssql

logger = logging.getLogger(__name__)

RETENSI_HARI = 30  # hapus data lebih dari N hari


class Command(BaseCommand):
    help = 'Ambil frekuensi per detik dari SYS_FREQ_HIS → simpan ke PostgreSQL, purge > 30 hari'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Tampilkan tanpa menyimpan',
        )

    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)
        tz_local = timezone.get_current_timezone()

        # ── Ambil data dari MSSQL ─────────────────────────────────────
        raw = mssql.get_freq_seconds(detik=70)  # 70 detik — cukup overlap
        if not raw:
            self.stdout.write('Tidak ada data dari MSSQL SYS_FREQ_HIS.')
            return

        # Konversi ke timezone-aware
        objs = []
        for dt_naive, hz in raw:
            try:
                dt_aware = timezone.make_aware(dt_naive, tz_local)
            except Exception:
                dt_aware = dt_naive.replace(tzinfo=timezone.utc)
            objs.append(SnapFreq(waktu=dt_aware, hz=hz))

        if dry_run:
            self.stdout.write(f'[DRY] {len(objs)} baris siap disimpan')
            return

        # ── Bulk insert, abaikan duplikat ────────────────────────────
        created = SnapFreq.objects.bulk_create(objs, ignore_conflicts=True)
        saved = len(created)

        # ── Auto-purge data > 30 hari ────────────────────────────────
        batas = timezone.now() - timezone.timedelta(days=RETENSI_HARI)
        deleted_count, _ = SnapFreq.objects.filter(waktu__lt=batas).delete()

        now_str = timezone.now().astimezone(tz_local).strftime('%Y-%m-%d %H:%M:%S')
        self.stdout.write(
            f"[{now_str}] saved={saved}/{len(objs)} purged={deleted_count}"
        )
