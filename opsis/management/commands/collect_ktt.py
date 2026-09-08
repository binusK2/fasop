"""
Management command: collect_ktt

Ambil snapshot beban konsumen tegangan tinggi (KTT) dari MSSQL `IND_LOAD` →
simpan ke PostgreSQL (opsis.SnapKtt).

Ada karena alasan yang sama dengan collect_trafo: `IND_LOAD` hanya menyimpan
nilai realtime yang ditimpa di tempat — tidak ada kolom waktu, tidak ada
histori. Command inilah yang membangun histori per menit untuk chart 24 jam
Beban KTT di dashboard.

Jalankan manual:
    python manage.py collect_ktt
    python manage.py collect_ktt --dry-run

Jadwal via crontab (tiap menit, sama seperti collect_live/collect_trafo):
    * * * * * cd /path/to/fasop && python manage.py collect_ktt >> /var/log/fasop/collect_ktt.log 2>&1
"""
import logging

from django.core.management.base import BaseCommand
from django.utils import timezone

from opsis import ktt as ktt_mod
from opsis.models import SnapKtt

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Ambil snapshot IND_LOAD (beban KTT) dari MSSQL dan simpan ke PostgreSQL'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Tampilkan data yang akan disimpan tanpa benar-benar menyimpan',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']

        # Dibaca lewat modul bersama, bukan mssql.get_beban_ktt() langsung:
        # nama konsumen dan pemisahan IND_TOTAL harus mengikuti aturan yang
        # sama dengan halaman dan API-nya.
        data = ktt_mod.baca_beban_ktt()
        rows = data['rows']

        if not rows:
            # Historian tak terjangkau. JANGAN menulis baris bernilai nol:
            # chart 24 jam-nya akan menampilkan jurang ke nol yang terbaca
            # sebagai "semua konsumen padam", padahal yang padam koneksinya.
            pesan = 'Tidak ada data KTT dari MSSQL — tidak ada yang disimpan.'
            self.stdout.write(self.style.WARNING(pesan))
            logger.warning('collect_ktt: %s', pesan)
            return

        # Floor ke menit supaya satu menit = satu baris per konsumen, dan
        # unique_together (analog, waktu) benar-benar menahan duplikat kalau
        # cron kebetulan jalan dua kali dalam satu menit.
        sekarang = timezone.now().replace(second=0, microsecond=0)

        objek = [SnapKtt(analog=r['analog'], waktu=sekarang, mw=r['value'])
                 for r in rows]
        # IND_TOTAL sengaja ikut disimpan — split_ktt() membuangnya dari daftar
        # konsumen, jadi ia harus diambil kembali dari data mentahnya.
        if data.get('total_mw') is not None:
            objek.append(SnapKtt(analog='IND_TOTAL', waktu=sekarang,
                                 mw=data['total_mw']))

        if dry_run:
            for o in objek:
                self.stdout.write(f'  [DRY] {o.analog:12s} = {o.mw}')
            self.stdout.write(self.style.SUCCESS(
                f'{len(objek)} baris akan disimpan pada {sekarang:%Y-%m-%d %H:%M}.'))
            return

        # ignore_conflicts: cron yang jalan dua kali dalam satu menit tidak
        # boleh menggagalkan seluruh batch.
        tersimpan = SnapKtt.objects.bulk_create(objek, ignore_conflicts=True)
        self.stdout.write(self.style.SUCCESS(
            f'{len(tersimpan)} dari {len(objek)} baris KTT disimpan '
            f'pada {sekarang:%Y-%m-%d %H:%M}.'))
