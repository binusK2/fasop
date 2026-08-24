"""
Management command: export_inspeksi_harian

Simpan laporan hasil inspeksi harian (Excel) ke folder arsip — isinya sama
persis dengan tombol "Export Excel" di halaman Hasil Inspeksi Harian, karena
keduanya memakai laporan.workbook_harian().

Crontab (tiap hari jam 12.00 waktu server):
    0 12 * * * cd /path/to/fasop && /path/to/venv/bin/python manage.py export_inspeksi_harian >> /var/log/fasop/export_inspeksi_harian.log 2>&1

Tujuan default diambil dari settings.INSPEKSI_EXPORT_DIR (env
INSPEKSI_EXPORT_DIR). Di server Linux, share Windows \\\\192.168.77.5\\fasop
harus sudah di-mount lebih dulu (CIFS) — command ini menulis ke path biasa,
bukan berbicara SMB sendiri. Lihat deploy/EXPORT_INSPEKSI_HARIAN.md.

Berkasnya ditulis per hari:
    <INSPEKSI_EXPORT_DIR>/<YYYY-MM>/Inspeksi_Harian_<YYYY-MM-DD>.xlsx

Menjalankan ulang di hari yang sama menimpa file hari itu (angka jam 12.00
digantikan angka terbaru), bukan menambah file baru.
"""
import os
from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from inspection.laporan import nama_file_harian, workbook_harian


class Command(BaseCommand):
    help = 'Simpan laporan Excel hasil inspeksi harian ke folder arsip'

    def add_arguments(self, parser):
        parser.add_argument('--tanggal', help='Tanggal laporan (YYYY-MM-DD), default hari ini')
        parser.add_argument('--days', type=int, default=1,
                            help='Jumlah hari ke belakang yang diekspor (default 1 = hari itu saja)')
        parser.add_argument('--dir', dest='folder',
                            help='Folder tujuan; default settings.INSPEKSI_EXPORT_DIR')
        parser.add_argument('--dry-run', action='store_true',
                            help='Tampilkan tujuan dan jumlah baris tanpa menulis file')

    def handle(self, *args, **options):
        from datetime import date

        folder = options.get('folder') or getattr(settings, 'INSPEKSI_EXPORT_DIR', '')
        if not folder:
            raise CommandError(
                'Folder tujuan belum diatur. Isi INSPEKSI_EXPORT_DIR di .env '
                '(mis. /mnt/fasop/inspeksi harian untuk share //192.168.77.5/fasop) '
                'atau jalankan dengan --dir.'
            )

        teks = options.get('tanggal')
        if teks:
            try:
                tanggal_akhir = date.fromisoformat(teks)
            except ValueError:
                raise CommandError(f'Format tanggal tidak dikenal: {teks} (pakai YYYY-MM-DD)')
        else:
            tanggal_akhir = timezone.localdate()

        hari = max(1, options.get('days') or 1)
        dry_run = options.get('dry_run', False)

        gagal = 0
        for i in range(hari):
            tanggal = tanggal_akhir - timedelta(days=i)
            try:
                self._ekspor_satu_hari(tanggal, folder, dry_run)
            except Exception as exc:               # noqa: BLE001 — satu hari gagal tidak menghentikan sisanya
                gagal += 1
                self.stderr.write(self.style.ERROR(f'  {tanggal}: GAGAL — {exc}'))

        if gagal:
            raise CommandError(f'{gagal} dari {hari} hari gagal diekspor.')

    def _ekspor_satu_hari(self, tanggal, folder, dry_run):
        tujuan_folder = os.path.join(folder, tanggal.strftime('%Y-%m'))
        nama          = nama_file_harian(tanggal)
        tujuan        = os.path.join(tujuan_folder, nama)

        if dry_run:
            self.stdout.write(f'  [dry-run] {tanggal} → {tujuan}')
            return

        os.makedirs(tujuan_folder, exist_ok=True)
        wb = workbook_harian(tanggal)

        # Tulis ke berkas sementara di folder yang sama lalu ganti nama, supaya
        # file arsip tidak pernah tertinggal separuh kalau share-nya putus di
        # tengah penulisan.
        sementara = os.path.join(tujuan_folder, f'.{nama}.tmp')
        wb.save(sementara)
        os.replace(sementara, tujuan)

        ukuran = os.path.getsize(tujuan)
        self.stdout.write(self.style.SUCCESS(
            f'  {tanggal} → {tujuan} ({ukuran // 1024} KB)'))
