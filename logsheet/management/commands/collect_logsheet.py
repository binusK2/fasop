"""
Kolektor logsheet — dijalankan cron tiap 30 menit (0,30 * * * *) mulai jam 00.
Untuk tiap LogsheetTitik aktif, ambil nilai terkini dari MSSQL SCADA (server
yang sama dengan OPSIS) dan simpan ke LogsheetNilai pada slot 30-menit saat ini.

    python manage.py collect_logsheet            # tulis slot sekarang
    python manage.py collect_logsheet --dry-run  # tampilkan tanpa menyimpan
    python manage.py collect_logsheet --slot 12 --tanggal 2026-07-27  # override

Pola query mengikuti makro lama:
    SELECT <kolom> FROM <tabel> WHERE <keykol>='<key>'
"""
import datetime
from django.core.management.base import BaseCommand
from django.utils import timezone


def slot_for(dt):
    """
    Slot 30-menit untuk waktu dt: 00:30 -> (tanggal, 0), 01:00 -> 1, …,
    24:00 (yakni 00:00 hari berikutnya) -> (tanggal kemarin, 47).
    Kembalikan (tanggal, slot).
    """
    minutes = dt.hour * 60 + dt.minute
    idx = round(minutes / 30) - 1          # 00:30 -> 0
    if idx < 0:                            # 00:00 -> slot 47 hari sebelumnya
        return (dt.date() - datetime.timedelta(days=1), 47)
    return (dt.date(), min(idx, 47))


class Command(BaseCommand):
    help = 'Ambil nilai logsheet dari MSSQL dan simpan ke slot 30-menit saat ini.'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true')
        parser.add_argument('--slot', type=int, default=None)
        parser.add_argument('--tanggal', default=None, help='YYYY-MM-DD override')

    def handle(self, *args, **opts):
        from logsheet.models import LogsheetTitik, LogsheetNilai
        from opsis import mssql

        now = timezone.localtime()
        tanggal, slot = slot_for(now)
        if opts['tanggal']:
            tanggal = datetime.date.fromisoformat(opts['tanggal'])
        if opts['slot'] is not None:
            slot = opts['slot']

        titik = list(LogsheetTitik.objects.filter(aktif=True)
                     .exclude(mssql_tabel='').exclude(mssql_kolom=''))
        if not titik:
            self.stdout.write(self.style.WARNING('Tidak ada titik terkonfigurasi.'))
            return

        if not mssql.is_reachable():
            self.stdout.write(self.style.ERROR('MSSQL tidak terjangkau — dilewati.'))
            return

        conn = mssql._get_connection()
        cur = conn.cursor()
        n_ok, n_err = 0, 0
        for t in titik:
            try:
                # kolom bisa berisi >1 kolom dipisah koma (mis. BUSBAR_A,BUSBAR_B)
                # -> ambil MAX nilai non-null (meniru P = MAX(A,B) di Excel).
                koloms = [k.strip() for k in t.mssql_kolom.split(',') if k.strip()]
                sel = ', '.join(koloms)
                sql = (f"SELECT {sel} FROM {t.mssql_tabel} WITH (NOLOCK) "
                       f"WHERE {t.mssql_keykol} = ?")
                cur.execute(sql, (t.mssql_key,))
                row = cur.fetchone()
                vals = [float(v) for v in row if v is not None] if row else []
                val = (max(vals) * (t.faktor or 1.0)) if vals else None
            except Exception as e:
                n_err += 1
                if opts['dry_run']:
                    self.stdout.write(self.style.ERROR(f'  {t.key}: ERROR {e}'))
                continue

            if opts['dry_run']:
                self.stdout.write(f'  {t.key} @ {tanggal} slot{slot} = {val}')
                n_ok += 1
                continue

            LogsheetNilai.objects.update_or_create(
                titik=t, tanggal=tanggal, slot=slot,
                defaults={'waktu': now, 'nilai': val})
            n_ok += 1

        conn.close()
        msg = f'{tanggal} slot{slot}: {n_ok} titik disimpan, {n_err} error.'
        self.stdout.write((self.style.WARNING('[dry-run] ') if opts['dry_run'] else '') +
                          self.style.SUCCESS(msg))
