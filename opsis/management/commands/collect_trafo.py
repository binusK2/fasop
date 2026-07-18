"""
Management command: collect_trafo
Ambil snapshot ALL_TRANS_DATA — trafo distribusi (BAY TRF52%/TRF42%) DAN
trafo IBT (BAY TRF65%/TRF54%) — dari MSSQL -> simpan ke PostgreSQL
(SnapTrafo, tabel yang sama; Trafo registry sudah membedakan keduanya lewat
prefix BAY). ALL_TRANS_DATA hanya berisi nilai realtime tanpa histori, jadi
command ini yang membangun histori per menit untuk chart 24 jam per trafo
(baik "Chart Trafo Distribusi" maupun "Chart Trafo IBT").

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
    help = 'Ambil snapshot ALL_TRANS_DATA (trafo distribusi + IBT) dari MSSQL dan simpan ke PostgreSQL'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Tampilkan data yang akan disimpan tanpa benar-benar menyimpan',
        )

    def _collect(self, label, rows, now, dry_run):
        """
        Simpan satu batch rows (distribusi ATAU IBT, format sama:
        site/bay/p/q/v/i) ke SnapTrafo. trafo_map di-refresh di sini karena
        _trafo_aktif_saja() bisa saja baru saja mendaftarkan trafo baru.
        Return (saved, skipped, missing, error).
        """
        if not rows:
            self.stdout.write(f'Tidak ada data trafo {label} dari MSSQL.')
            return 0, 0, 0, 0

        trafo_map = {(t.site, t.bay): t for t in Trafo.objects.filter(aktif=True)}
        saved = skipped = missing = error = 0

        for r in rows:
            trafo = trafo_map.get((r['site'], r['bay']))
            if not trafo:
                missing += 1
                continue

            if dry_run:
                self.stdout.write(f"  [DRY][{label}] {trafo} | P={r['p']}")
                saved += 1
                continue

            try:
                _, created = SnapTrafo.objects.get_or_create(
                    trafo=trafo,
                    waktu=now,
                    defaults={'p': r['p']},
                )
                if created:
                    saved += 1
                else:
                    skipped += 1  # sudah ada data untuk menit ini
            except Exception as e:
                logger.error('collect_trafo error for %s: %s', trafo, e, exc_info=True)
                error += 1

        return saved, skipped, missing, error

    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)

        if not getattr(settings, 'MSSQL_HOST', ''):
            self.stdout.write('MSSQL_HOST belum diset — lewati.')
            return

        now = timezone.now().replace(second=0, microsecond=0)

        # _trafo_aktif_saja juga otomatis mendaftarkan trafo baru yang belum
        # ada di admin (opsis.Trafo), sama seperti dipakai halaman beban_trafo/beban_trafo_ibt.
        s1, sk1, m1, e1 = self._collect('distribusi', _trafo_aktif_saja(mssql.get_beban_trafo()), now, dry_run)
        s2, sk2, m2, e2 = self._collect('IBT', _trafo_aktif_saja(mssql.get_beban_trafo_ibt()), now, dry_run)

        prefix = '[DRY-RUN] ' if dry_run else ''
        self.stdout.write(
            f"{prefix}[{now:%Y-%m-%d %H:%M}] "
            f"saved={s1 + s2} skipped={sk1 + sk2} missing={m1 + m2} error={e1 + e2}"
        )
