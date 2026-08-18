"""
Management command: probe_dmp

Diagnosa read-only tabel Daya Mampu (dbo.KIT_DMP) — menampilkan nama kolom dan
beberapa baris pertama, supaya bisa ditentukan kolom mana yang diisi ke
Opsis -> Pembangkit -> "Daya Mampu — dbo.KIT_DMP" (Kolom DMN / Kolom DMP)
di site admin.

Jalankan:
    python manage.py probe_dmp
    python manage.py probe_dmp --limit 5
"""
from django.core.management.base import BaseCommand
from opsis import mssql


class Command(BaseCommand):
    help = 'Tampilkan struktur dan isi awal tabel KIT_DMP (DMN/DMP) dari MSSQL'

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=10,
                            help='Jumlah baris contoh yang ditampilkan (default 10)')

    def handle(self, *args, **opts):
        hasil = mssql.probe_dmp(limit=opts['limit'])
        self.stdout.write(f"Tabel  : {hasil['tabel']}")
        if hasil['error']:
            self.stdout.write(self.style.ERROR(f"Error  : {hasil['error']}"))
            return

        self.stdout.write(f"Kolom  : {', '.join(hasil['kolom']) or '(kosong)'}")
        self.stdout.write(f"Baris  : {len(hasil['rows'])} contoh\n")
        for row in hasil['rows']:
            isi = ' | '.join(f'{k}={row[k]}' for k in hasil['kolom'])
            self.stdout.write(f'  {isi}')

        if not hasil['rows']:
            self.stdout.write(self.style.WARNING('Tabel kosong / tidak ada baris.'))
            return
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(
            'Isi nama kolom DMN/DMP di site admin: Opsis -> Pembangkit -> '
            'bagian "Daya Mampu — dbo.KIT_DMP".'
        ))
