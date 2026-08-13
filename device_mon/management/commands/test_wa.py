"""
Management command: test_wa
Kirim satu pesan uji ke grup WhatsApp (OpenWA) untuk memverifikasi
konfigurasi Early Warning tanpa menunggu RTU benar-benar DOWN, atau
konfigurasi grup alarm inspeksi (--target inspection).

Contoh:
    python manage.py test_wa
    python manage.py test_wa --target inspection
    python manage.py test_wa --pesan "Tes notifikasi FASOP"
"""
from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from device_mon.notifications import kirim_wa, _targets as _targets_rtu
from inspection.notifications import _targets as _targets_inspection


class Command(BaseCommand):
    help = 'Kirim pesan uji ke grup WhatsApp (OpenWA) untuk cek konfigurasi'

    def add_arguments(self, parser):
        parser.add_argument('--pesan', default=None, help='Isi pesan uji')
        parser.add_argument('--target', default='rtu', choices=['rtu', 'inspection'],
                             help='rtu (default, WA_CHAT_IDS) atau inspection (WA_CHAT_IDS_INSPECTION)')

    def handle(self, *args, **options):
        now = timezone.now().astimezone(timezone.get_current_timezone())
        target = options['target']
        label = 'Early Warning RTU' if target == 'rtu' else 'Alarm Inspeksi'
        pesan = options['pesan'] or (
            f'🔔 *Tes {label} FASOP*\n'
            f'Konfigurasi WhatsApp berhasil.\n'
            f'Waktu: {now:%d-%m-%Y %H:%M:%S}'
        )

        chat_ids = _targets_rtu() if target == 'rtu' else _targets_inspection()

        # Ringkasan konfigurasi (API key disamarkan)
        key = getattr(settings, 'WA_API_KEY', '') or ''
        self.stdout.write(f'Konfigurasi (target={target}):')
        self.stdout.write(f'  WA_ALERT_ENABLED = {getattr(settings, "WA_ALERT_ENABLED", False)}')
        self.stdout.write(f'  WA_API_BASE      = {getattr(settings, "WA_API_BASE", "")}')
        self.stdout.write(f'  WA_SESSION_ID    = {getattr(settings, "WA_SESSION_ID", "")}')
        self.stdout.write(f'  chat_ids         = {chat_ids}')
        self.stdout.write(f'  WA_API_KEY       = {"***" + key[-4:] if key else "(kosong)"}')

        terkirim, total, ket = kirim_wa(pesan, chat_ids=chat_ids)
        if terkirim > 0:
            self.stdout.write(self.style.SUCCESS(
                f'Terkirim ke {terkirim}/{total} grup. Keterangan: {ket}'))
        else:
            self.stdout.write(self.style.ERROR(
                f'Gagal kirim (0/{total}). Keterangan: {ket}'))
