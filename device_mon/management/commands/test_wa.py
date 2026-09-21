"""
Management command: test_wa
Kirim satu pesan uji ke grup WhatsApp (WAHA) untuk memverifikasi konfigurasi
Early Warning tanpa menunggu RTU benar-benar DOWN, alarm inspeksi
(--target inspection), atau blast host Zabbix (--target zabbix).

Contoh:
    python manage.py test_wa
    python manage.py test_wa --target inspection
    python manage.py test_wa --target zabbix
    python manage.py test_wa --pesan "Tes notifikasi FASOP"
    python manage.py test_wa --hanya-status      # cek sesi saja, tanpa kirim

Catatan: --target zabbix mengetes tujuan *default* (WA_CHAT_IDS_ZABBIX).
Host yang memakai kolom "Grup WA Khusus" diuji lewat action "Kirim pesan
uji WA" di Admin > Host Zabbix.
"""
from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from device_mon.notifications import (kirim_wa, sesi_wa,
                                      _build_headers,
                                      _targets as _targets_rtu,
                                      zbx_targets_default as _targets_zabbix)
from inspection.notifications import _targets as _targets_inspection


class Command(BaseCommand):
    help = 'Kirim pesan uji ke grup WhatsApp (WAHA) untuk cek konfigurasi'

    def add_arguments(self, parser):
        parser.add_argument('--pesan', default=None, help='Isi pesan uji')
        parser.add_argument('--target', default='rtu',
                             choices=['rtu', 'inspection', 'zabbix'],
                             help='rtu (default, WA_CHAT_IDS), inspection '
                                  '(WA_CHAT_IDS_INSPECTION), atau zabbix (WA_CHAT_IDS_ZABBIX)')
        parser.add_argument('--hanya-status', action='store_true',
                            dest='hanya_status',
                            help='Hanya periksa status sesi WAHA, tanpa mengirim pesan')

    # -- Pra-periksa status sesi -------------------------------------
    # WAHA membalas HTTP 4xx yang bentuknya sama untuk "gateway mati",
    # "API key salah", dan "sesi belum discan QR" — padahal ketiganya
    # menuntut tindakan yang sama sekali berbeda. Status sesi memisahkan
    # ketiganya sebelum satu pesan pun dikirim.
    def _cek_sesi(self):
        base = (getattr(settings, 'WA_API_BASE', '') or '').rstrip('/')
        if not base:
            return None

        try:
            import requests
        except ImportError:
            return None

        sesi = sesi_wa()
        url = f'{base}/api/sessions/{sesi}'
        try:
            resp = requests.get(url, headers=_build_headers(),
                                timeout=getattr(settings, 'WA_TIMEOUT', 10))
        except Exception as e:
            self.stdout.write(self.style.ERROR(
                f'  status sesi      = gateway tidak terjangkau ({e})'))
            self.stdout.write('    -> cek WA_API_BASE dan apakah container WAHA jalan.')
            return False

        if resp.status_code in (401, 403):
            self.stdout.write(self.style.ERROR(
                f'  status sesi      = HTTP {resp.status_code} (ditolak)'))
            self.stdout.write('    -> WA_API_KEY tidak cocok dengan WAHA_API_KEY di container WAHA.')
            return False
        if resp.status_code == 404:
            self.stdout.write(self.style.ERROR(
                f'  status sesi      = sesi "{sesi}" tidak ada di WAHA'))
            self.stdout.write('    -> buat sesinya di dashboard WAHA, atau samakan WA_SESSION_ID.')
            return False
        if not (200 <= resp.status_code < 300):
            self.stdout.write(self.style.ERROR(
                f'  status sesi      = HTTP {resp.status_code} {resp.text[:120]}'))
            return False

        try:
            status = (resp.json() or {}).get('status') or '?'
        except ValueError:
            self.stdout.write(self.style.WARNING(
                '  status sesi      = balasan bukan JSON'))
            return None

        if status == 'WORKING':
            self.stdout.write(self.style.SUCCESS(f'  status sesi      = {status}'))
            return True

        self.stdout.write(self.style.WARNING(f'  status sesi      = {status}'))
        if status == 'SCAN_QR_CODE':
            self.stdout.write('    -> sesi belum tersambung: scan QR di dashboard WAHA.')
        elif status == 'STOPPED':
            self.stdout.write('    -> sesi berhenti: start dari dashboard WAHA.')
        elif status == 'FAILED':
            self.stdout.write('    -> restart sesi; kalau tetap gagal, logout lalu scan QR lagi.')
        return False

    def handle(self, *args, **options):
        now = timezone.now().astimezone(timezone.get_current_timezone())
        target = options['target']
        label = {
            'rtu': 'Early Warning RTU',
            'inspection': 'Alarm Inspeksi',
            'zabbix': 'Blast Zabbix',
        }[target]
        pesan = options['pesan'] or (
            f'🔔 *Tes {label} FASOP*\n'
            f'Konfigurasi WhatsApp berhasil.\n'
            f'Waktu: {now:%d-%m-%Y %H:%M:%S}'
        )

        chat_ids = {
            'rtu': _targets_rtu,
            'inspection': _targets_inspection,
            'zabbix': _targets_zabbix,
        }[target]()

        # Ringkasan konfigurasi (API key disamarkan)
        key = getattr(settings, 'WA_API_KEY', '') or ''
        sesi_env = getattr(settings, 'WA_SESSION_ID', '') or ''
        self.stdout.write(f'Konfigurasi (gateway WAHA, target={target}):')
        self.stdout.write(f'  WA_ALERT_ENABLED = {getattr(settings, "WA_ALERT_ENABLED", False)}')
        self.stdout.write(f'  WA_API_BASE      = {getattr(settings, "WA_API_BASE", "")}')
        self.stdout.write(f'  sesi             = {sesi_wa()}'
                          f'{"" if sesi_env else "  (WA_SESSION_ID kosong -> bawaan WAHA)"}')
        self.stdout.write(f'  chat_ids         = {chat_ids}')
        self.stdout.write(f'  WA_API_KEY       = {"***" + key[-4:] if key else "(kosong)"}')

        self._cek_sesi()

        if options['hanya_status']:
            return

        terkirim, total, ket = kirim_wa(pesan, chat_ids=chat_ids)
        if terkirim > 0:
            self.stdout.write(self.style.SUCCESS(
                f'Terkirim ke {terkirim}/{total} grup. Keterangan: {ket}'))
        else:
            self.stdout.write(self.style.ERROR(
                f'Gagal kirim (0/{total}). Keterangan: {ket}'))
