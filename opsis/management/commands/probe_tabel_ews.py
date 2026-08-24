"""
Management command: probe_tabel_ews

Diagnosa read-only sebuah tabel MSSQL — menampilkan nama kolom dan beberapa
baris pertama, supaya bisa ditentukan kolom mana yang diisi ke
Opsis -> Titik EWS -> "Sumber Data Realtime (MSSQL)" di site admin.

Jalankan:
    python manage.py probe_tabel_ews dbo.KIT_REALTIME
    python manage.py probe_tabel_ews dbo.SYS_FREQ_RT --limit 5
"""
from django.core.management.base import BaseCommand
from opsis import mssql


class Command(BaseCommand):
    help = 'Tampilkan struktur dan isi awal sebuah tabel MSSQL (untuk memetakan Titik EWS)'

    def add_arguments(self, parser):
        parser.add_argument('tabel', help='Nama tabel MSSQL, mis. dbo.KIT_REALTIME')
        parser.add_argument('--limit', type=int, default=10,
                            help='Jumlah baris contoh yang ditampilkan (default 10)')

    def handle(self, *args, **opts):
        hasil = mssql.probe_tabel(opts['tabel'], limit=opts['limit'])
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
            'Isi nama kolom di site admin: Opsis -> Titik EWS -> bagian '
            '"Sumber Data Realtime (MSSQL)": Kolom Nilai, Kolom Kunci, Nilai Kunci.'
        ))
