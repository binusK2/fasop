"""
Management command: cek_armada_kit

Bandingkan daftar pembangkit di EMPAT tempat yang harus sejalan:

    1. dbo.KIT_REALTIME   — sumber angka Dashboard (live MW/MVAR)
    2. dbo.HIS_MEAS_KIT   — sumber angka Respons Pembangkit (riwayat per unit)
    3. opsis.Pembangkit   — master data FASOP (menentukan apa yang tampil di Dashboard)
    4. RESPON_PLANTS      — registry Respons Kit (menentukan apa yang dianalisis)

Kenapa perlu: total MW Dashboard dan Respons Pembangkit pernah berbeda 32 MW,
dan penyebabnya bukan perhitungan — kedua tabel historian memuat armada yang
tidak sama. BMPP WOLO (~58 MW) ada di KIT_REALTIME tapi sama sekali tidak
direkam di HIS_MEAS_KIT, sementara PLTMH (~27 MW) sebaliknya. Selisih seperti
itu tidak terlihat dari layar mana pun sampai ada yang membandingkan manual.

Jalankan:
    python manage.py cek_armada_kit
    python manage.py cek_armada_kit --menit 240   # jendela pindai HIS_MEAS_KIT
"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Bandingkan armada pembangkit di KIT_REALTIME, HIS_MEAS_KIT, Pembangkit, dan RESPON_PLANTS.'

    def add_arguments(self, parser):
        parser.add_argument('--menit', type=int, default=120,
                            help='Jendela pindai HIS_MEAS_KIT (default 120 menit)')

    def handle(self, *args, **opts):
        from opsis import mssql
        from opsis.models import Pembangkit
        from opsis.respon_registry import RESPON_PLANTS

        # ── 1. KIT_REALTIME ──
        realtime = set()
        try:
            conn = mssql._get_connection()
            cur = conn.cursor()
            cur.execute('SELECT RTRIM(KIT) FROM dbo.KIT_REALTIME WITH (NOLOCK)')
            realtime = {r[0].strip().upper() for r in cur.fetchall() if r[0]}
            conn.close()
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'KIT_REALTIME gagal dibaca: {e}'))

        # ── 2. HIS_MEAS_KIT ──
        info = mssql.list_kit_codes(opts['menit'])
        kits = info.get('kits') or {}
        if isinstance(kits, dict):
            histori = {k.strip().upper() for k in kits}
        else:
            histori = {(k[0] if isinstance(k, (tuple, list)) else k).strip().upper()
                       for k in kits}

        # ── 3. Pembangkit (master FASOP) ──
        master = {p.kit_source().strip().upper(): p.nama
                  for p in Pembangkit.objects.filter(aktif=True)}

        # ── 4. RESPON_PLANTS ──
        registry = {b1.strip().upper() for us in RESPON_PLANTS.values() for b1, _ in us}

        semua = sorted(realtime | histori | set(master) | registry)

        self.stdout.write('')
        self.stdout.write('%-14s %-26s %-3s %-3s %-3s %-3s' % (
            'KIT', 'Nama (Pembangkit)', 'RT', 'HIS', 'PBK', 'RSP'))
        self.stdout.write('-' * 62)
        for k in semua:
            self.stdout.write('%-14s %-26s %-3s %-3s %-3s %-3s' % (
                k, (master.get(k) or '-')[:25],
                'v' if k in realtime else '.',
                'v' if k in histori else '.',
                'v' if k in master else '.',
                'v' if k in registry else '.'))

        self.stdout.write('')
        self.stdout.write('RT=KIT_REALTIME (Dashboard)   HIS=HIS_MEAS_KIT (Respons)')
        self.stdout.write('PBK=opsis.Pembangkit          RSP=RESPON_PLANTS')

        def _lapor(judul, kode, saran, gaya):
            if not kode:
                return
            self.stdout.write('')
            self.stdout.write(gaya(f'{judul} ({len(kode)}):'))
            for k in sorted(kode):
                nama = master.get(k)
                self.stdout.write(f'   {k}' + (f'  — {nama}' if nama else ''))
            self.stdout.write(f'   → {saran}')

        # Tampil di Dashboard tapi Respons tidak akan pernah melihatnya.
        _lapor('DASHBOARD PUNYA, RESPONS TIDAK BISA',
               (realtime & set(master)) - histori,
               'Tidak direkam di HIS_MEAS_KIT. Tidak bisa diperbaiki dari FASOP — '
               'minta pengelola historian menambahkan KIT ini ke perekaman.',
               self.style.ERROR)

        # Ada datanya di historian, tapi tidak muncul di Dashboard.
        _lapor('ADA DI HISTORIAN, TIDAK DI DASHBOARD',
               histori - set(master),
               'Belum ada barisnya di Admin → Opsis → Pembangkit. Tambahkan bila '
               'memang bagian dari sistem, agar total Dashboard tidak kurang.',
               self.style.WARNING)

        # Terdaftar untuk dianalisis tapi datanya sudah tidak ada.
        _lapor('DI RESPON_PLANTS TAPI TIDAK ADA DATANYA',
               registry - histori,
               'Kode lama / sudah diganti. Bersihkan dari opsis/respon_registry.py '
               'supaya tidak menyesatkan.',
               self.style.WARNING)

        # Punya data historis tapi tidak ikut dianalisis.
        _lapor('PUNYA DATA HISTORIS TAPI TIDAK DIANALISIS',
               histori - registry,
               'Tambahkan ke RESPON_PLANTS bila perlu ikut analisis respons.',
               self.style.WARNING)

        cocok = realtime & histori & set(master) & registry
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(
            f'Sejalan di keempat tempat: {len(cocok)} dari {len(semua)} KIT.'))
