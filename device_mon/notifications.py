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
