"""
Impor data HOP (Hari Operasi) batu bara & BBM dari workbook konfirmasi stok
Sulawesi ke tabel HopPembangkit / HopSnapshot.

    python manage.py import_hop path/ke/Konfirmasi_Batubara_Sulawesi.xlsx
    python manage.py import_hop file.xlsx --dry-run
"""
from django.core.management.base import BaseCommand, CommandError
from opsis import hop as hop_import


class Command(BaseCommand):
    help = 'Impor data HOP (Hari Operasi) batu bara & BBM dari file .xlsx'

    def add_arguments(self, parser):
        parser.add_argument('file', help='Path ke workbook .xlsx konfirmasi stok')
        parser.add_argument('--dry-run', action='store_true',
                            help='Parse & tampilkan ringkasan tanpa menyimpan')

    def handle(self, *args, **opts):
        path = opts['file']
        try:
            data = hop_import.parse_workbook(path)
        except FileNotFoundError:
            raise CommandError(f'File tidak ditemukan: {path}')
        except Exception as e:
            raise CommandError(f'Gagal membaca workbook: {e}')

        if not data:
            self.stdout.write(self.style.WARNING(
                'Tidak ada baris pembangkit terbaca (cek sheet "Batubara"/"BBM").'))
            return

        per_kat = {}
        for d in data:
            per_kat.setdefault(d['kategori'], 0)
            per_kat[d['kategori']] += 1
        for kat, n in per_kat.items():
            self.stdout.write(f'  {kat}: {n} pembangkit')

        if opts['dry_run']:
            self.stdout.write(self.style.WARNING('[dry-run] tidak menyimpan.'))
            return

        hasil = hop_import.simpan(data)
        self.stdout.write(self.style.SUCCESS(
            f"Impor selesai — {hasil['pembangkit']} pembangkit, "
            f"{hasil['snapshot']} snapshot, tanggal terakhir "
            f"{hasil['tanggal_terakhir']}."))
