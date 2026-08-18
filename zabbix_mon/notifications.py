"""
Notifikasi in-app (bukan WhatsApp) untuk transisi state host Zabbix.

Memakai helper generik notifikasi.views.notif_ke_am() (lihat "Notification
fan-out" di CLAUDE.md) — bukan modul WA terpisah seperti device_mon, karena
Zabbix sendiri sudah punya jalur alerting sendiri (email/telegram/dsb di
sisi Zabbix Action); FASOP cukup menandai di pusat notifikasi in-app
supaya AM/superuser melihatnya saat login.
"""
import logging

from django.utils import timezone

logger = logging.getLogger(__name__)


def notif_transisi(host, state, dur_tutup_menit=None):
    """Kirim notifikasi in-app ke AM + superuser saat host Zabbix PROBLEM/pulih.

    Tidak pernah raise — kegagalan cukup dicatat ke log.
    """
    try:
        from notifikasi.views import notif_ke_am
        from fasop.hashids_helper import encode

        if state == 'PROBLEM':
            judul = f'Zabbix: {host.nama} PROBLEM'
            pesan = host.problem_name or 'Trigger problem terdeteksi.'
            if host.severity:
                pesan = f'[{host.severity}] {pesan}'
            level = 'danger'
        else:
            judul = f'Zabbix: {host.nama} pulih (OK)'
            if dur_tutup_menit is not None:
                if dur_tutup_menit < 60:
                    durasi = f'{dur_tutup_menit} menit'
                else:
                    j, m = divmod(dur_tutup_menit, 60)
                    durasi = f'{j} jam {m} menit' if m else f'{j} jam'
                pesan = f'Kembali OK setelah {durasi} problem.'
            else:
                pesan = 'Kembali OK.'
            level = 'success'

        url = f'/zabbix/host/{encode(host.pk)}/'
        notif_ke_am(tipe='zabbix_state', judul=judul, pesan=pesan, level=level, url=url)
    except Exception as e:
        logger.error('notif_transisi error [%s %s]: %s', getattr(host, 'nama', '?'), state, e)
