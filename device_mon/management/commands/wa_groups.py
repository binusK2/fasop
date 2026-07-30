"""
Management command: wa_groups
Bantu menemukan chatId grup WhatsApp dari OpenWA, untuk mengisi
WA_CHAT_IDS di .env. chatId grup berakhiran "@g.us".

Contoh:
    python manage.py wa_groups

Butuh WA_API_BASE, WA_SESSION_ID, dan WA_API_KEY sudah terisi di .env.
Alternatif: lihat langsung di dashboard OpenWA (http://<host>:2785).
"""
import json

from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Tampilkan daftar grup WhatsApp (chatId) dari sesi OpenWA'

    def handle(self, *args, **options):
        base    = (getattr(settings, 'WA_API_BASE', '') or '').rstrip('/')
        session = getattr(settings, 'WA_SESSION_ID', '') or ''
        key     = getattr(settings, 'WA_API_KEY', '') or ''

        if not base or not session:
            self.stdout.write(self.style.ERROR(
                'WA_API_BASE / WA_SESSION_ID belum diisi di .env'))
            return

        try:
            import requests
        except ImportError:
            self.stdout.write(self.style.ERROR(
                'Paket "requests" belum terpasang (pip install requests)'))
            return

        url = f'{base}/api/sessions/{session}/groups'
        headers = {'Content-Type': 'application/json'}
        if key:
            headers['X-API-Key'] = key
        timeout = getattr(settings, 'WA_TIMEOUT', 10)

        self.stdout.write(f'GET {url}')
        try:
            resp = requests.get(url, headers=headers, timeout=timeout)
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Request gagal: {e}'))
            return

        self.stdout.write(f'HTTP {resp.status_code}')
        try:
            data = resp.json()
        except ValueError:
            self.stdout.write(resp.text[:2000])
            return

        self.stdout.write(self.style.SUCCESS('Daftar grup (cari field chatId / id @g.us):'))
        self.stdout.write(json.dumps(data, indent=2, ensure_ascii=False)[:4000])
