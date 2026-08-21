"""
Notifikasi transisi state host Zabbix — dua jalur yang independen:

1. In-app  : selalu, ke AM + superuser lewat helper generik
             notifikasi.views.notif_ke_am() (lihat "Notification fan-out"
             di CLAUDE.md).
2. WhatsApp: hanya untuk host yang dicentang `wa_alert` di Admin, dikirim
             lewat gateway OpenWA yang sama dengan Early Warning RTU
             (device_mon.notifications.kirim_wa). Default mati supaya host
             baru hasil sync_zabbix tidak langsung membanjiri grup.

Dipanggil dari dua titik transisi yang sudah ada — `sync_zabbix` (pull API)
dan `zabbix_mon.views.webhook_receiver` (push webhook) — lewat satu entry
point `notif_transisi()`, jadi menambah jalur notifikasi baru cukup di sini
tanpa menyentuh kedua pemanggil.

Prinsip: tidak pernah melempar exception ke pemanggil. Kegagalan satu jalur
tidak boleh membatalkan jalur lain, dan tidak boleh menggagalkan sync/webhook.
"""
import logging

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


def _durasi_str(menit):
    """120 -> '2 jam', 90 -> '1 jam 30 menit', 45 -> '45 menit'."""
    if menit is None:
        return '-'
    if menit < 60:
        return f'{menit} menit'
    j, m = divmod(menit, 60)
    return f'{j} jam {m} menit' if m else f'{j} jam'


def _now_wib():
    tz = timezone.get_current_timezone()
    return timezone.now().astimezone(tz).strftime('%d-%m-%Y %H:%M:%S')


# ── Jalur 1: notifikasi in-app ────────────────────────────────────────
def _notif_in_app(host, state, dur_tutup_menit=None):
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
            pesan = f'Kembali OK setelah {_durasi_str(dur_tutup_menit)} problem.'
        else:
            pesan = 'Kembali OK.'
        level = 'success'

    url = f'/zabbix/host/{encode(host.pk)}/'
    notif_ke_am(tipe='zabbix_state', judul=judul, pesan=pesan, level=level, url=url)


# ── Jalur 2: blast WhatsApp (opt-in per host) ─────────────────────────
def _split(raw):
    return [c.strip() for c in (raw or '').split(',') if c.strip()]


def targets_default():
    """chatId tujuan default untuk seluruh host Zabbix.

    WA_CHAT_IDS_ZABBIX -> WA_CHAT_IDS. Fallback ke grup RTU disengaja:
    sebagian besar deployment cuma punya satu grup operasional, dan blast
    tetap tidak jalan sampai `wa_alert` dicentang manual per host.
    """
    raw = (getattr(settings, 'WA_CHAT_IDS_ZABBIX', '') or '').strip()
    return _split(raw or getattr(settings, 'WA_CHAT_IDS', ''))


def _targets(host):
    """chatId tujuan untuk satu host — kolom `wa_chat_ids` menimpa default."""
    khusus = _split(host.wa_chat_ids)
    return khusus or targets_default()


def pesan_problem(host):
    tz = timezone.get_current_timezone()
    jam = (host.state_sejak.astimezone(tz).strftime('%H:%M:%S')
           if host.state_sejak else _now_wib())
    return (
        '🔴 *EARLY WARNING — PROBLEM*\n'
        f'Perangkat : {host.nama}\n'
        f'Lokasi    : {host.lokasi or "-"}\n'
        f'Severity  : {host.severity or "-"}\n'
        f'Problem   : {host.problem_name or "-"}\n'
        f'Sejak     : {jam}\n'
        '\n_FASOP — Monitoring Zabbix_'
    )


def pesan_ok(host, durasi_menit=None):
    return (
        '🟢 *PERANGKAT PULIH (OK)*\n'
        f'Perangkat    : {host.nama}\n'
        f'Lokasi       : {host.lokasi or "-"}\n'
        f'Durasi problem: {_durasi_str(durasi_menit)}\n'
        f'Kembali OK   : {_now_wib()}\n'
        '\n_FASOP — Monitoring Zabbix_'
    )


def _min_severity(host):
    try:
        return int(host.wa_min_severity)
    except (TypeError, ValueError):
        return 0


def _problem_terkirim(host):
    """True kalau blast PROBLEM terakhir host ini benar-benar terkirim.

    Dipakai supaya tidak ada pesan "pulih" yang muncul di grup untuk problem
    yang pesannya sendiri tidak pernah masuk (di bawah ambang severity, atau
    gateway sedang mati).
    """
    from zabbix_mon.models import ZabbixAlertLog

    terakhir = ZabbixAlertLog.objects.filter(host=host).order_by('-created_at').first()
    return bool(terakhir and terakhir.jenis == 'PROBLEM' and terakhir.terkirim)


def alert_wa(host, state, dur_tutup_menit=None):
    """Blast satu transisi host ke grup WhatsApp; catat ke ZabbixAlertLog.

    Return True kalau ada minimal satu tujuan yang berhasil dikirimi.
    Tidak pernah raise.
    """
    from device_mon.notifications import kirim_wa
    from zabbix_mon.models import ZabbixAlertLog

    if not host.wa_alert:
        return False

    jenis = 'PROBLEM' if state == 'PROBLEM' else 'OK'

    if jenis == 'PROBLEM':
        from zabbix_mon.zabbix_api import severity_index
        if severity_index(host.severity) < _min_severity(host):
            ZabbixAlertLog.objects.create(
                host=host, jenis=jenis, pesan=pesan_problem(host), terkirim=False,
                keterangan=f'Dilewati: severity "{host.severity or "-"}" di bawah ambang '
                           f'{host.get_wa_min_severity_display()}.'[:255],
            )
            return False
        pesan = pesan_problem(host)
    else:
        if not _problem_terkirim(host):
            # Problem-nya tidak pernah masuk grup — pesan pulihnya jadi tanpa konteks.
            return False
        pesan = pesan_ok(host, durasi_menit=dur_tutup_menit)

    chat_ids = _targets(host)
    if not chat_ids:
        ZabbixAlertLog.objects.create(
            host=host, jenis=jenis, pesan=pesan, terkirim=False,
            keterangan='Tujuan WA kosong — isi WA_CHAT_IDS_ZABBIX di .env atau '
                       'kolom "Grup WA Khusus" pada host ini.',
        )
        return False

    terkirim, total, ket = kirim_wa(pesan, chat_ids=chat_ids)
    ZabbixAlertLog.objects.create(
        host=host, jenis=jenis, pesan=pesan,
        terkirim=terkirim > 0, keterangan=(ket or '')[:255],
    )
    return terkirim > 0


# ── Entry point dipanggil sync_zabbix + webhook_receiver ──────────────
def notif_transisi(host, state, dur_tutup_menit=None):
    """Fan-out satu transisi state host ke seluruh jalur notifikasi.

    Kedua jalur dibungkus terpisah: WhatsApp gagal tidak boleh membuat
    notifikasi in-app ikut hilang, dan sebaliknya.
    """
    try:
        _notif_in_app(host, state, dur_tutup_menit=dur_tutup_menit)
    except Exception as e:
        logger.error('notif_transisi in-app error [%s %s]: %s',
                     getattr(host, 'nama', '?'), state, e)

    try:
        alert_wa(host, state, dur_tutup_menit=dur_tutup_menit)
    except Exception as e:
        logger.error('notif_transisi WA error [%s %s]: %s',
                     getattr(host, 'nama', '?'), state, e)
