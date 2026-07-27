"""
Impor master titik logsheet dari berkas pemetaan JSON hasil ekstraksi workbook
(logsheet/data/*.json). Tiap record: key, kategori, besaran, nama, sheet, baris,
mssql_tabel/kolom/keykol/key, faktor(optional).

    python manage.py import_logsheet_master                # semua kategori
    python manage.py import_logsheet_master --kategori kit # satu file kit_*.json
    python manage.py import_logsheet_master --dry-run

Aman dijalankan ulang (update_or_create by key). Field yang diubah admin
(mis. aktif) tidak ditimpa selain yang ada di JSON.
"""
import json
import os
import glob
from django.core.management.base import BaseCommand

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data')

FIELDS = ('kategori', 'besaran', 'nama', 'sheet', 'baris',
          'mssql_tabel', 'mssql_kolom', 'mssql_keykol', 'mssql_key', 'faktor')


class Command(BaseCommand):
    help = 'Impor master titik logsheet dari logsheet/data/*.json'

    def add_arguments(self, parser):
        parser.add_argument('--kategori', default=None,
                            help='Batasi ke file <kategori>_titik.json (mis. kit).')
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **opts):
        from logsheet.models import LogsheetTitik

        if opts['kategori']:
            files = [os.path.join(DATA_DIR, f'{opts["kategori"]}_titik.json')]
        else:
            files = sorted(glob.glob(os.path.join(DATA_DIR, '*_titik.json')))
        files = [f for f in files if os.path.exists(f)]
        if not files:
            self.stdout.write(self.style.WARNING(f'Tidak ada file JSON di {DATA_DIR}.'))
            return

        n_new, n_upd = 0, 0
        for path in files:
            recs = json.load(open(path, encoding='utf-8'))
            self.stdout.write(f'{os.path.basename(path)}: {len(recs)} record')
            for r in recs:
                defaults = {k: r.get(k) for k in FIELDS if k in r}
                if opts['dry_run']:
                    continue
                obj, created = LogsheetTitik.objects.update_or_create(
                    key=r['key'], defaults=defaults)
                n_new += int(created)
                n_upd += int(not created)

        if opts['dry_run']:
            self.stdout.write(self.style.WARNING('[dry-run] tidak menyimpan.'))
        else:
            self.stdout.write(self.style.SUCCESS(
                f'Selesai — {n_new} titik baru, {n_upd} diperbarui.'))
