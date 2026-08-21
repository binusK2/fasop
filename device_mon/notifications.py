"""
Early Warning WhatsApp untuk device_mon (status RTU).

Mengirim notifikasi ke grup WhatsApp via OpenWA (gateway self-hosted)
saat RTU DOWN dan saat pulih (UP). Dipanggil oleh management command
collect_rtu pada titik transisi state.

Prinsip: fungsi di modul ini TIDAK PERNAH melempar exception ke pemanggil —
kegagalan kirim dicatat (log + RTUAlertLog) tapi collect_rtu harus tetap
jalan. Konfigurasi via .env (lihat fasop/settings.py blok "Early Warning
WhatsApp").

┌─ SPESIFIK API OpenWA ──────────────────────────────────────────────┐
│ POST {WA_API_BASE}/api/sessions/{WA_SESSION_ID}/messages/send-text  │
│   header  X-API-Key: <WA_API_KEY>                                   │
│   body    {"chatId": "<id>", "text": "<pesan>"}                     │
│ Untuk grup, chatId berakhiran "@g.us".                              │
│ Bila ganti gateway lain, cukup sesuaikan _build_url / _build_headers│
│ / _build_payload di bawah.                                          │
└────────────────────────────────────────────────────────────────────┘
"""
import logging

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


# ── Bagian spesifik API OpenWA ───────────────────────────────────────
def _build_url():
    """URL endpoint send-text untuk sesi yang dikonfigurasi."""
    base = (getattr(settings, 'WA_API_BASE', '') or '').rstrip('/')
    session = getattr(settings, 'WA_SESSION_ID', '') or ''
    return f'{base}/api/sessions/{session}/messages/send-text'


def _build_headers():
    """Header HTTP untuk request OpenWA (autentikasi X-API-Key)."""
    headers = {'Content-Type': 'application/json'}
    if settings.WA_API_KEY:
        headers['X-API-Key'] = settings.WA_API_KEY
    return headers


def _build_payload(chat_id, pesan):
    """Body JSON send-text untuk satu tujuan (chatId grup / personal)."""
    return {
        'chatId': chat_id,
        'text': pesan,
    }
# ──────────────────────────────────────────────────────────────────────


def _targets():
    """Daftar chatId tujuan dari WA_CHAT_IDS (comma-separated)."""
    raw = getattr(settings, 'WA_CHAT_IDS', '') or ''
    return [c.strip() for c in raw.split(',') if c.strip()]


def kirim_wa(pesan, chat_ids=None):
    """Kirim `pesan` ke semua chatId tujuan.

    Return: (jumlah_terkirim, jumlah_target, keterangan_str).
    Tidak pernah raise.
    """
    if not getattr(settings, 'WA_ALERT_ENABLED', False):
        return 0, 0, 'WA_ALERT_ENABLED=False'

    base = getattr(settings, 'WA_API_BASE', '') or ''
    session = getattr(settings, 'WA_SESSION_ID', '') or ''
    targets = chat_ids if chat_ids is not None else _targets()
    if not base or not session or not targets:
        return 0, 0, 'WA_API_BASE / WA_SESSION_ID / WA_CHAT_IDS belum diisi'

    try:
        import requests
    except ImportError:
        logger.error('WA: paket "requests" belum terpasang (pip install requests)')
        return 0, 0, 'requests belum terpasang'

    url = _build_url()
    timeout = getattr(settings, 'WA_TIMEOUT', 10)
    headers = _build_headers()

    terkirim = 0
    catatan = []
    for cid in targets:
        try:
            resp = requests.post(
                url,
                json=_build_payload(cid, pesan),
                headers=headers,
                timeout=timeout,
            )
            if 200 <= resp.status_code < 300:
                terkirim += 1
            else:
                body = (resp.text or '')[:200]
                catatan.append(f'{cid}: HTTP {resp.status_code} {body}')
                logger.error('WA kirim gagal [%s]: HTTP %s %s',
                             cid, resp.status_code, body)
        except Exception as e:            # network / timeout / dll
            catatan.append(f'{cid}: {e}')
            logger.error('WA kirim error [%s]: %s', cid, e)

    ket = 'OK' if not catatan else '; '.join(catatan)
    return terkirim, len(targets), ket


# ── Formatter pesan ───────────────────────────────────────────────────
def _now_wib():
    tz = timezone.get_current_timezone()
    return timezone.now().astimezone(tz).strftime('%d-%m-%Y %H:%M:%S')


def pesan_down(rtu, sejak=None):
    tz = timezone.get_current_timezone()
    jam = (sejak.astimezone(tz).strftime('%H:%M:%S') if sejak else _now_wib())
    lokasi = rtu.lokasi or '-'
    return (
        '🔴 *EARLY WARNING — RTU DOWN*\n'
        f'RTU     : {rtu.nama}\n'
        f'Lokasi  : {lokasi}\n'
        f'Status  : DOWN sejak {jam}\n'
        '\n_FASOP — Monitoring RTU_'
    )


def pesan_up(rtu, durasi_menit=None):
    lokasi = rtu.lokasi or '-'
    if durasi_menit is None:
        durasi = '-'
    elif durasi_menit < 60:
        durasi = f'{durasi_menit} menit'
    else:
        j, m = divmod(durasi_menit, 60)
        durasi = f'{j} jam {m} menit' if m else f'{j} jam'
    return (
        '🟢 *RTU PULIH (UP)*\n'
        f'RTU        : {rtu.nama}\n'
        f'Lokasi     : {lokasi}\n'
        f'Durasi down: {durasi}\n'
        f'Kembali UP : {_now_wib()}\n'
        '\n_FASOP — Monitoring RTU_'
    )


# ── Entry point dipanggil collect_rtu ─────────────────────────────────
def alert_rtu(rtu, jenis, sejak=None, durasi_menit=None):
    """Kirim Early Warning untuk satu RTU dan catat ke RTUAlertLog.

    jenis: 'DOWN' atau 'UP'. Tidak pernah raise.
    """
    from device_mon.models import RTUAlertLog   # hindari circular import

    if not getattr(rtu, 'wa_alert', True):
        return False

    try:
        if jenis == 'DOWN':
            pesan = pesan_down(rtu, sejak=sejak)
        else:
            pesan = pesan_up(rtu, durasi_menit=durasi_menit)

        terkirim, total, ket = kirim_wa(pesan)

        RTUAlertLog.objects.create(
            rtu=rtu,
            jenis=jenis,
            pesan=pesan,
            terkirim=terkirim > 0,
            keterangan=(ket or '')[:255],
        )
        return terkirim > 0
    except Exception as e:
        logger.error('alert_rtu error [%s %s]: %s', getattr(rtu, 'nama', '?'), jenis, e)
        return False


# ===========================================================================
#  Notifikasi transisi state host Zabbix - dua jalur yang independen:
#
#  1. In-app  : selalu, ke AM + superuser lewat helper generik
#               notifikasi.views.notif_ke_am() (lihat "Notification fan-out"
#               di CLAUDE.md).
#  2. WhatsApp: hanya untuk host yang dicentang `wa_alert` di Admin, lewat
#               kirim_wa() yang sama dengan Early Warning RTU di atas. Default
#               mati supaya host baru hasil sync_zabbix tidak langsung
#               membanjiri grup.
#
#  Dipanggil dari dua titik transisi - `sync_zabbix` (pull API) dan
#  `views.zbx_webhook_receiver` (push webhook) - lewat satu entry point
#  notif_zabbix_transisi(), jadi menambah jalur notifikasi baru cukup di sini
#  tanpa menyentuh kedua pemanggil.
# ===========================================================================
def _durasi_str(menit):
    """120 -> '2 jam', 90 -> '1 jam 30 menit', 45 -> '45 menit'."""
    if menit is None:
        return '-'
    if menit < 60:
        return f'{menit} menit'
    j, m = divmod(menit, 60)
    return f'{j} jam {m} menit' if m else f'{j} jam'


def _lokasi_str(host):
    """ZabbixHost.lokasi adalah FK ke devices.SiteLocation (boleh kosong)."""
    return host.lokasi.nama if host.lokasi else '-'


def _notif_zbx_in_app(host, state, dur_tutup_menit=None):
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

    url = f'/device-mon/zabbix/host/{encode(host.pk)}/'
    notif_ke_am(tipe='zabbix_state', judul=judul, pesan=pesan, level=level, url=url)


# -- Blast WhatsApp host Zabbix (opt-in per host) ----------------------
def _split(raw):
    return [c.strip() for c in (raw or '').split(',') if c.strip()]


def zbx_targets_default():
    """chatId tujuan default untuk seluruh host Zabbix.

    WA_CHAT_IDS_ZABBIX -> WA_CHAT_IDS. Fallback ke grup RTU disengaja:
    sebagian besar deployment cuma punya satu grup operasional, dan blast
    tetap tidak jalan sampai `wa_alert` dicentang manual per host.
    """
    raw = (getattr(settings, 'WA_CHAT_IDS_ZABBIX', '') or '').strip()
    return _split(raw or getattr(settings, 'WA_CHAT_IDS', ''))


def zbx_targets(host):
    """chatId tujuan untuk satu host - kolom `wa_chat_ids` menimpa default."""
    return _split(host.wa_chat_ids) or zbx_targets_default()


def pesan_zbx_problem(host):
    tz = timezone.get_current_timezone()
    jam = (host.state_sejak.astimezone(tz).strftime('%H:%M:%S')
           if host.state_sejak else _now_wib())
    return (
        '\U0001F534 *EARLY WARNING \u2014 PROBLEM*\n'
        f'Perangkat : {host.nama}\n'
        f'Lokasi    : {_lokasi_str(host)}\n'
        f'Severity  : {host.severity or "-"}\n'
        f'Problem   : {host.problem_name or "-"}\n'
        f'Sejak     : {jam}\n'
        '\n_FASOP \u2014 Monitoring Zabbix_'
    )


def pesan_zbx_ok(host, durasi_menit=None):
    return (
        '\U0001F7E2 *PERANGKAT PULIH (OK)*\n'
        f'Perangkat     : {host.nama}\n'
        f'Lokasi        : {_lokasi_str(host)}\n'
        f'Durasi problem: {_durasi_str(durasi_menit)}\n'
        f'Kembali OK    : {_now_wib()}\n'
        '\n_FASOP \u2014 Monitoring Zabbix_'
    )


def _zbx_min_severity(host):
    try:
        return int(host.wa_min_severity)
    except (TypeError, ValueError):
        return 0


def _zbx_problem_terkirim(host):
    """True kalau blast PROBLEM terakhir host ini benar-benar terkirim.

    Dipakai supaya tidak ada pesan "pulih" yang muncul di grup untuk problem
    yang pesannya sendiri tidak pernah masuk (di bawah ambang severity, atau
    gateway sedang mati).
    """
    from device_mon.models import ZabbixAlertLog

    terakhir = ZabbixAlertLog.objects.filter(host=host).order_by('-created_at').first()
    return bool(terakhir and terakhir.jenis == 'PROBLEM' and terakhir.terkirim)


def alert_zabbix(host, state, dur_tutup_menit=None):
    """Blast satu transisi host ke grup WhatsApp; catat ke ZabbixAlertLog.

    Return True kalau ada minimal satu tujuan yang berhasil dikirimi.
    Tidak pernah raise.
    """
    from device_mon.models import ZabbixAlertLog
    from device_mon.zabbix_api import severity_index

    if not host.wa_alert:
        return False

    jenis = 'PROBLEM' if state == 'PROBLEM' else 'OK'

    if jenis == 'PROBLEM':
        if severity_index(host.severity) < _zbx_min_severity(host):
            ZabbixAlertLog.objects.create(
                host=host, jenis=jenis, pesan=pesan_zbx_problem(host), terkirim=False,
                keterangan=f'Dilewati: severity "{host.severity or "-"}" di bawah ambang '
                           f'{host.get_wa_min_severity_display()}.'[:255],
            )
            return False
        pesan = pesan_zbx_problem(host)
    else:
        if not _zbx_problem_terkirim(host):
            # Problem-nya tidak pernah masuk grup - pesan pulihnya jadi tanpa konteks.
            return False
        pesan = pesan_zbx_ok(host, durasi_menit=dur_tutup_menit)

    chat_ids = zbx_targets(host)
    if not chat_ids:
        ZabbixAlertLog.objects.create(
            host=host, jenis=jenis, pesan=pesan, terkirim=False,
            keterangan='Tujuan WA kosong - isi WA_CHAT_IDS_ZABBIX di .env atau '
                       'kolom "Grup WA Khusus" pada host ini.',
        )
        return False

    terkirim, total, ket = kirim_wa(pesan, chat_ids=chat_ids)
    ZabbixAlertLog.objects.create(
        host=host, jenis=jenis, pesan=pesan,
        terkirim=terkirim > 0, keterangan=(ket or '')[:255],
    )
    return terkirim > 0


# -- Entry point dipanggil sync_zabbix + zbx_webhook_receiver ----------
def notif_zabbix_transisi(host, state, dur_tutup_menit=None):
    """Fan-out satu transisi state host Zabbix ke seluruh jalur notifikasi.

    Kedua jalur dibungkus terpisah: WhatsApp gagal tidak boleh membuat
    notifikasi in-app ikut hilang, dan sebaliknya. Tidak pernah raise.
    """
    try:
        _notif_zbx_in_app(host, state, dur_tutup_menit=dur_tutup_menit)
    except Exception as e:
        logger.error('notif_zabbix_transisi in-app error [%s %s]: %s',
                     getattr(host, 'nama', '?'), state, e)

    try:
        alert_zabbix(host, state, dur_tutup_menit=dur_tutup_menit)
    except Exception as e:
        logger.error('notif_zabbix_transisi WA error [%s %s]: %s',
                     getattr(host, 'nama', '?'), state, e)
