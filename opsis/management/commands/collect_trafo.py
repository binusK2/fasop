"""
Management command: collect_trafo
Ambil snapshot ALL_TRANS_DATA (trafo distribusi, BAY TRF52%/TRF42%) dari
MSSQL -> simpan ke PostgreSQL (SnapTrafo). ALL_TRANS_DATA hanya berisi nilai
realtime tanpa histori, jadi command ini yang membangun histori per menit
untuk chart 24 jam per trafo.

Jalankan manual:
    python manage.py collect_trafo

Jadwal via crontab (tiap menit, sama seperti collect_live):
    * * * * * cd /path/to/fasop && python manage.py collect_trafo >> /var/log/fasop/collect_trafo.log 2>&1
"""
import logging
from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone
from opsis.models import Trafo, SnapTrafo
from opsis import mssql
from opsis.views import _trafo_aktif_saja

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Ambil snapshot ALL_TRANS_DATA (trafo distribusi) dari MSSQL dan simpan ke PostgreSQL'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Tampilkan data yang akan disimpan tanpa benar-benar menyimpan',
        )

    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)

        if not getattr(settings, 'MSSQL_HOST', ''):
            self.stdout.write('MSSQL_HOST belum diset — lewati (data akan dummy).')
            return

        # _trafo_aktif_saja juga otomatis mendaftarkan trafo baru yang belum
        # ada di admin (opsis.Trafo), sama seperti dipakai halaman beban_trafo.
        rows = _trafo_aktif_saja(mssql.get_beban_trafo())
        if not rows:
            self.stdout.write('Tidak ada data trafo distribusi dari MSSQL.')
            return

        trafo_map = {(t.site, t.bay): t for t in Trafo.objects.filter(aktif=True)}

        now = timezone.now().replace(second=0, microsecond=0)
        saved = skipped = missing = error = 0

        for r in rows:
            trafo = trafo_map.get((r['site'], r['bay']))
            if not trafo:
                missing += 1
                continue

            if dry_run:
                self.stdout.write(f"  [DRY] {trafo} | P={r['p']} | Q={r['q']}")
                saved += 1
                continue

            try:
                _, created = SnapTrafo.objects.get_or_create(
                    trafo=trafo,
                    waktu=now,
                    defaults={'p': r['p'], 'q': r['q']},
                )
                if created:
                    saved += 1
                else:
                    skipped += 1  # sudah ada data untuk menit ini
            except Exception as e:
                logger.error('collect_trafo error for %s: %s', trafo, e, exc_info=True)
                error += 1

        prefix = '[DRY-RUN] ' if dry_run else ''
        self.stdout.write(
            f"{prefix}[{now:%Y-%m-%d %H:%M}] "
            f"saved={saved} skipped={skipped} missing={missing} error={error}"
        )
