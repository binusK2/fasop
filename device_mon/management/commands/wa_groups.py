"""
Management command: wa_groups
Bantu menemukan chatId grup WhatsApp dari WAHA, untuk mengisi WA_CHAT_IDS
(atau WA_CHAT_IDS_ZABBIX / WA_CHAT_IDS_INSPECTION) di .env. chatId grup
selalu berakhiran "@g.us".

Contoh:
    python manage.py wa_groups
    python manage.py wa_groups --cari "SCADA"
    python manage.py wa_groups --limit 200 --json

Butuh WA_API_BASE (dan WA_API_KEY bila gateway-nya dikunci) terisi di .env.
WA_SESSION_ID boleh dikosongkan — artinya sesi "default" bawaan WAHA.
Alternatif: lihat langsung di dashboard WAHA (http://<host>:3000/dashboard).

API: GET {WA_API_BASE}/api/{sesi}/groups?exclude=participants
     header X-Api-Key.
"""
import json

from django.conf import settings
from django.core.management.base import BaseCommand

from device_mon.notifications import _build_headers, sesi_wa


def _id_grup(g):
    """Ambil chatId dari satu entri grup.

    Bentuk `id` berbeda per engine WAHA: WEBJS mengembalikan objek
    ({"_serialized": "...@g.us"}), NOWEB/GOWS mengembalikan string. Kalau
    hanya satu bentuk yang dibaca, daftar keluar kosong di engine lainnya
    padahal grupnya jelas ada.
    """
    raw = g.get('id')
    if isinstance(raw, dict):
        return raw.get('_serialized') or ''
    return raw or ''


def _nama_grup(g):
    """Nama grup — `name` (GOWS/NOWEB) atau `subject` (WEBJS)."""
    return g.get('name') or g.get('subject') or '(tanpa nama)'


class Command(BaseCommand):
    help = 'Tampilkan daftar grup WhatsApp (chatId) dari sesi WAHA'

    def add_arguments(self, parser):
        parser.add_argument('--cari', default=None,
                            help='Saring menurut potongan nama grup (abaikan huruf besar/kecil)')
        parser.add_argument('--limit', type=int, default=100,
                            help='Jumlah grup maksimum yang diambil (default 100)')
        parser.add_argument('--json', action='store_true',
                            help='Cetak JSON mentah dari WAHA, bukan tabel')

    def handle(self, *args, **options):
        base = (getattr(settings, 'WA_API_BASE', '') or '').rstrip('/')
        if not base:
            self.stdout.write(self.style.ERROR('WA_API_BASE belum diisi di .env'))
            return

        try:
            import requests
        except ImportError:
            self.stdout.write(self.style.ERROR(
                'Paket "requests" belum terpasang (pip install requests)'))
            return

        sesi = sesi_wa()
        # exclude=participants: daftar peserta bisa ribuan baris dan tidak
        # dipakai sama sekali di sini — tanpa ini request gampang timeout.
        url = f'{base}/api/{sesi}/groups'
        params = {'exclude': 'participants', 'limit': options['limit']}
        timeout = getattr(settings, 'WA_TIMEOUT', 10)

        self.stdout.write(f'GET {url}  (sesi: {sesi})')
        try:
            resp = requests.get(url, headers=_build_headers(),
                                params=params, timeout=timeout)
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Request gagal: {e}'))
            return

        self.stdout.write(f'HTTP {resp.status_code}')
        try:
            data = resp.json()
        except ValueError:
            self.stdout.write(resp.text[:2000])
            return

        if not (200 <= resp.status_code < 300):
            self.stdout.write(self.style.ERROR(
                json.dumps(data, indent=2, ensure_ascii=False)[:2000]))
            return

        if options['json']:
            self.stdout.write(json.dumps(data, indent=2, ensure_ascii=False)[:8000])
            return

        # WAHA mengembalikan list; sebagian engine membungkusnya di key.
        grup = data if isinstance(data, list) else (data.get('groups') or [])
        cari = (options['cari'] or '').lower()
        if cari:
            grup = [g for g in grup if cari in _nama_grup(g).lower()]

        if not grup:
            self.stdout.write(self.style.WARNING(
                'Tidak ada grup yang cocok. Coba tanpa --cari, naikkan --limit, '
                'atau cek sesi WAHA sudah WORKING (python manage.py test_wa).'))
            return

        self.stdout.write(self.style.SUCCESS(
            f'{len(grup)} grup — salin kolom chatId ke WA_CHAT_IDS di .env:'))
        lebar = max(len(_nama_grup(g)) for g in grup)
        for g in sorted(grup, key=lambda x: _nama_grup(x).lower()):
            self.stdout.write(f'  {_nama_grup(g):<{lebar}}  {_id_grup(g)}')
