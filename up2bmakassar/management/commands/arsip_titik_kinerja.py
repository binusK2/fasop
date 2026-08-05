"""
Management command: arsip_titik_kinerja

Simpan daftar titik ber-flag kinerja=1 dari OFDB ke file CSV. Read-only terhadap
OFDB -- tidak mengubah apa pun.

JALANKAN INI SEBELUM MENYENTUH SyncDataPoints DI 19.1.

Alasannya: syncoffline/apps/sync_offline/jobs/points.py menulis kinerja = 0 pada
INSERT maupun UPDATE, dan menghapus baris scd_c_point yang sudah tidak ada di
Spectrum. Begitu job itu dijalankan lagi setelah lama berhenti, flag kinerja=1
yang tersisa akan habis dan sebagian barisnya kemungkinan terhapus -- padahal
baris itulah satu-satunya catatan titik mana saja yang dulu dinilai kinerjanya
(nama station/bay/element-nya ada di kolom path).

    python manage.py arsip_titik_kinerja
    python manage.py arsip_titik_kinerja --output /path/titik_kinerja.csv
"""
import csv
from datetime import datetime

from django.core.management.base import BaseCommand
from django.utils import timezone

from up2bmakassar import ofdb


class Command(BaseCommand):
    help = 'Arsipkan daftar titik kinerja=1 dari OFDB ke CSV (read-only)'

    def add_arguments(self, parser):
        parser.add_argument('--output', type=str, default=None,
                            help='Path file CSV. Default: titik_kinerja_ofdb_<tanggal>.csv '
                                 'di direktori kerja sekarang.')

    def handle(self, *args, **options):
        path = options.get('output') or (
            f'titik_kinerja_ofdb_{timezone.localdate():%Y%m%d}.csv'
        )

        try:
            conn = ofdb.get_connection()
        except Exception as e:
            self.stderr.write(f'[ERROR] Gagal konek OFDB: {e}')
            return

        try:
            rows = ofdb.get_titik_kinerja_semua(conn.cursor())
        finally:
            conn.close()

        if not rows:
            self.stderr.write(
                '[PERINGATAN] Tidak ada titik dengan kinerja=1 di scd_c_point. '
                'Kalau ini tidak diharapkan, JANGAN jalankan SyncDataPoints dulu.'
            )
            return

        with open(path, 'w', newline='', encoding='utf-8') as f:
            w = csv.writer(f)
            w.writerow(ofdb.TITIK_KINERJA_KOLOM)
            for row in rows:
                w.writerow(['' if v is None else v for v in row])

        per_jenis = {}
        for row in rows:
            per_jenis[row[1] or '-'] = per_jenis.get(row[1] or '-', 0) + 1

        self.stdout.write(f'{len(rows)} titik kinerja diarsipkan ke {path}')
        for jenis, jumlah in sorted(per_jenis.items()):
            self.stdout.write(f'    {jenis:<18} {jumlah}')
        self.stdout.write(
            'Simpan file ini di luar server 19.1 sebelum SyncDataPoints dijalankan lagi.'
        )
