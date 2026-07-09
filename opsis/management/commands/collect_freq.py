"""
Management command: collect_freq
Ambil data frekuensi per detik dari SYS_FREQ_HIS → simpan ke PostgreSQL (SnapFreq).
Ambil juga snapshot frekuensi area (Sultra/Sulteng/Baubau/Luwuk) dari tabel
realtime TRANS_xxx_RT → simpan ke SnapFreqArea (satu baris per area per run,
karena sumbernya snapshot nilai terkini, bukan historian per detik).
Auto-purge: hapus data lebih dari 30 hari secara otomatis.

Jadwal via crontab (setiap menit, berbarengan dengan collect_live):
    * * * * * cd /path/to/fasop && /home/fasop/fasop/venv/bin/python manage.py collect_freq >> /var/log/fasop/collect_freq.log 2>&1

Estimasi storage: 86.400 baris/hari × 30 hari ≈ 2.6 juta baris (~130 MB) untuk SnapFreq.
SnapFreqArea jauh lebih kecil (4 area × 1 baris/menit × 30 hari ≈ 172.800 baris).
"""
import logging
from django.core.management.base import BaseCommand
from django.utils import timezone
from opsis.models import SnapFreq, SnapFreqArea
from opsis import mssql

logger = logging.getLogger(__name__)

RETENSI_HARI = 30  # hapus data lebih dari N hari

AREA_FREQ_FUNCS = {
    'sultra':  mssql.get_freq_sultra,
    'sulteng': mssql.get_freq_sulteng,
    'baubau':  mssql.get_freq_baubau,
    'luwuk':   mssql.get_freq_luwuk,
}


class Command(BaseCommand):
    help = 'Ambil frekuensi sistem+area dari MSSQL → simpan ke PostgreSQL, purge > 30 hari'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Tampilkan tanpa menyimpan',
        )

    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)
        tz_local = timezone.get_current_timezone()
        now = timezone.now()

        # ── Frekuensi Sistem — historian per detik (SYS_FREQ_HIS) ─────
        raw = mssql.get_freq_seconds(detik=70)  # 70 detik — cukup overlap
        objs = []
        for dt_naive, hz in raw:
            try:
                dt_aware = timezone.make_aware(dt_naive, tz_local)
            except Exception:
                dt_aware = dt_naive.replace(tzinfo=timezone.utc)
            objs.append(SnapFreq(waktu=dt_aware, hz=hz))

        # ── Frekuensi Area — snapshot nilai terkini (TRANS_xxx_RT) ────
        area_objs = []
        for area, func in AREA_FREQ_FUNCS.items():
            try:
                hz = func()
            except Exception as e:
                logger.error('collect_freq area %s error: %s', area, e)
                hz = None
            if hz is not None:
                area_objs.append(SnapFreqArea(area=area, waktu=now, hz=hz))

        if dry_run:
            self.stdout.write(f'[DRY] sistem={len(objs)} area={len(area_objs)} siap disimpan')
            return

        if not objs and not area_objs:
            self.stdout.write('Tidak ada data dari MSSQL.')
            return

        # ── Bulk insert, abaikan duplikat ────────────────────────────
        saved = len(SnapFreq.objects.bulk_create(objs, ignore_conflicts=True)) if objs else 0
        saved_area = len(SnapFreqArea.objects.bulk_create(area_objs, ignore_conflicts=True)) if area_objs else 0

        # ── Auto-purge data > 30 hari ────────────────────────────────
        batas = now - timezone.timedelta(days=RETENSI_HARI)
        deleted_count, _      = SnapFreq.objects.filter(waktu__lt=batas).delete()
        deleted_area_count, _ = SnapFreqArea.objects.filter(waktu__lt=batas).delete()

        now_str = now.astimezone(tz_local).strftime('%Y-%m-%d %H:%M:%S')
        self.stdout.write(
            f"[{now_str}] sistem: saved={saved}/{len(objs)} purged={deleted_count} | "
            f"area: saved={saved_area}/{len(area_objs)} purged={deleted_area_count}"
        )
