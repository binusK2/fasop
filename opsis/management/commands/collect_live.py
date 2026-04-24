"""
Management command: collect_live
Ambil snapshot KIT_REALTIME dari MSSQL → simpan ke PostgreSQL (SnapLive + SnapUnit).

Jalankan manual:
    python manage.py collect_live

Jadwal via crontab (setiap 5 menit):
    */5 * * * * cd /path/to/fasop && python manage.py collect_live >> /var/log/fasop/collect_live.log 2>&1

Atau tiap menit (resolusi lebih tinggi untuk ML):
    * * * * * cd /path/to/fasop && python manage.py collect_live >> /var/log/fasop/collect_live.log 2>&1
"""
import logging
from django.core.management.base import BaseCommand
from django.utils import timezone
from opsis.models import Pembangkit, SnapLive, SnapUnit
from opsis import mssql

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Ambil snapshot KIT_REALTIME dari MSSQL dan simpan ke PostgreSQL'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Tampilkan data yang akan disimpan tanpa benar-benar menyimpan',
        )

    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)
        pembangkit_list = list(Pembangkit.objects.filter(aktif=True))

        if not pembangkit_list:
            self.stdout.write('Tidak ada pembangkit aktif.')
            return

        result = mssql.get_live_data(pembangkit_list)

        # Floor ke menit → idempotent: jika dijalankan 2x dalam menit sama, tidak duplikat
        now = timezone.now().replace(second=0, microsecond=0)
        frekuensi = result.get('frekuensi_sistem')
        saved = skipped = dummy = error = 0

        for p in pembangkit_list:
            d = result['data'].get(p.kode)
            if not d:
                continue

            if d.get('is_dummy'):
                dummy += 1
                continue  # jangan simpan data simulasi

            if dry_run:
                self.stdout.write(
                    f"  [DRY] {p.kode} | MW={d.get('mw')} | MVAR={d.get('mvar')} "
                    f"| Hz={frekuensi} | units={len(d.get('units', []))}"
                )
                saved += 1
                continue

            try:
                snap, created = SnapLive.objects.get_or_create(
                    pembangkit=p,
                    waktu=now,
                    defaults={
                        'mw':        d.get('mw'),
                        'mvar':      d.get('mvar'),
                        'frekuensi': frekuensi,
                    }
                )
                if created:
                    for unit in d.get('units', []):
                        SnapUnit.objects.create(
                            snap=snap,
                            nama=unit['nama'],
                            mw=unit.get('mw'),
                            mvar=unit.get('mvar'),
                        )
                    saved += 1
                else:
                    skipped += 1  # sudah ada data untuk menit ini
            except Exception as e:
                logger.error('collect_live error for %s: %s', p.kode, e, exc_info=True)
                error += 1

        prefix = '[DRY-RUN] ' if dry_run else ''
        self.stdout.write(
            f"{prefix}[{now:%Y-%m-%d %H:%M}] "
            f"saved={saved} skipped={skipped} dummy={dummy} error={error}"
        )
