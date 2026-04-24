"""
Management command: collect_rtu
Ambil status RTU dari dbo.RTU_ALL_STATE (MSSQL) setiap menit.
Deteksi transisi state (UP↔DOWN) dan simpan ke RTULog (PostgreSQL).
Auto-purge: log > 1 tahun dihapus otomatis.

Crontab (tiap menit):
    * * * * * cd /path/to/fasop && /path/to/venv/bin/python manage.py collect_rtu >> /var/log/fasop/collect_rtu.log 2>&1
"""
import logging
from django.core.management.base import BaseCommand
from django.utils import timezone
from device_mon.models import RTU, RTULog
from opsis import mssql   # reuse koneksi MSSQL yang sudah ada

logger = logging.getLogger(__name__)

RETENSI_HARI = 365   # hapus log lebih dari 1 tahun


class Command(BaseCommand):
    help = 'Ambil status RTU dari MSSQL → deteksi transisi → simpan RTULog'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true',
                            help='Tampilkan output tanpa menyimpan')

    def handle(self, *args, **options):
        dry_run  = options.get('dry_run', False)
        tz_local = timezone.get_current_timezone()
        now      = timezone.now()

        # ── Ambil data dari MSSQL ─────────────────────────────────────
        try:
            rows = mssql.get_rtu_state()   # list of (nama, state, state_sejak)
        except Exception as e:
            self.stderr.write(f'[ERROR] Gagal query RTU_ALL_STATE: {e}')
            return

        if not rows:
            self.stdout.write('Tidak ada data dari RTU_ALL_STATE.')
            return

        transisi = 0
        error    = 0

        for nama, state, state_sejak in rows:
            try:
                state = (state or '').strip().upper()
                if state not in ('UP', 'DOWN'):
                    continue

                # Konversi state_sejak ke timezone-aware
                if state_sejak and state_sejak.tzinfo is None:
                    state_sejak = timezone.make_aware(state_sejak, tz_local)

                if dry_run:
                    self.stdout.write(f'[DRY] {nama}: {state} sejak {state_sejak}')
                    continue

                # Ambil atau buat RTU
                rtu, created = RTU.objects.get_or_create(nama=nama)

                prev_state   = rtu.state
                prev_sejak   = rtu.state_sejak

                if prev_state != state or created:
                    # ── Transisi state terdeteksi ──────────────────────
                    # 1. Tutup log sebelumnya (yang masih terbuka)
                    open_log = RTULog.objects.filter(rtu=rtu, selesai__isnull=True).first()
                    if open_log:
                        selesai = state_sejak or now
                        dur     = max(0, int((selesai - open_log.mulai).total_seconds() / 60))
                        open_log.selesai      = selesai
                        open_log.durasi_menit = dur
                        open_log.save(update_fields=['selesai', 'durasi_menit'])

                    # 2. Buat log baru untuk state saat ini
                    RTULog.objects.create(
                        rtu   = rtu,
                        state = state,
                        mulai = state_sejak or now,
                    )

                    # 3. Update RTU master
                    rtu.state       = state
                    rtu.state_sejak = state_sejak or now
                    rtu.save(update_fields=['state', 'state_sejak'])

                    self.stdout.write(
                        f'  [TRANSISI] {nama}: {prev_state} → {state}'
                        f' sejak {(state_sejak or now).astimezone(tz_local):%H:%M:%S}'
                    )
                    transisi += 1

                else:
                    # State sama, update state_sejak jika berbeda (data refresh MSSQL)
                    if state_sejak and rtu.state_sejak != state_sejak:
                        rtu.state_sejak = state_sejak
                        rtu.save(update_fields=['state_sejak'])

            except Exception as e:
                logger.error(f'collect_rtu error [{nama}]: {e}')
                error += 1

        # ── Auto-purge log > 1 tahun ──────────────────────────────────
        if not dry_run:
            batas = now - timezone.timedelta(days=RETENSI_HARI)
            deleted, _ = RTULog.objects.filter(mulai__lt=batas).delete()
        else:
            deleted = 0

        now_str = now.astimezone(tz_local).strftime('%Y-%m-%d %H:%M:%S')
        self.stdout.write(
            f'[{now_str}] rtu={len(rows)} transisi={transisi} error={error} purged={deleted}'
        )
