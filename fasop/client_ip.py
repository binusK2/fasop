"""
IP klien yang sebenarnya — SATU-SATUNYA tempat FASOP membacanya.

Dipakai log login (`devices.signals`), audit log (`auditlog.utils`), catatan
pemakaian kunci API (`api.auth`), dan penguncian login django-axes
(`AXES_CLIENT_IP_CALLABLE`). Jangan membaca `X-Forwarded-For` sendiri di
tempat lain.

Jalur permintaan di produksi (dua-duanya lewat nginx di server yang sama):

    internet → Cloudflare → cloudflared → nginx → gunicorn
    jaringan kantor (http://IP-internal) → nginx → gunicorn

Akibatnya `REMOTE_ADDR` di Django selalu alamat nginx (127.0.0.1), bukan
pengguna. Dua cara lama yang SALAH, dan masing-masing pernah dipakai:

- `REMOTE_ADDR` saja (django-axes bawaan): semua orang tercatat 127.0.0.1,
  sehingga kunci "username + IP" praktis jadi kunci per-username — siapa pun
  dari internet bisa mengunci akun superuser dengan 5x salah password, dan
  kuncinya tidak pernah lepas sendiri (`AXES_COOLOFF_TIME` tidak diatur).
- Elemen PERTAMA `X-Forwarded-For`: elemen itu ditulis pengirim sendiri.
  Cloudflare dan nginx MENAMBAHKAN alamat di belakangnya, tidak menimpa,
  jadi header `X-Forwarded-For: 1.2.3.4` dari penyerang membuat log login
  mencatat 1.2.3.4.

Yang benar: percayai header hanya kalau permintaan datang dari proxy yang
dikenal (`PROXY_TEPERCAYA`), lalu baca `X-Forwarded-For` dari KANAN — alamat
yang ditambahkan proxy tepercaya kita sendiri — dan ambil alamat pertama yang
bukan proxy tepercaya. Bagian kiri yang dikarang pengirim tidak pernah
tercapai. Itu berlaku untuk kedua jalur di atas selama nginx memakai
`proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;` (menambahkan,
bukan menimpa).

`CF-Connecting-IP` sengaja TIDAK dipakai: di jalur jaringan kantor permintaan
tidak lewat Cloudflare, jadi header itu bisa diisi siapa saja.
"""
import ipaddress
from functools import lru_cache

from django.conf import settings

PROXY_TEPERCAYA_BAWAAN = ('127.0.0.1', '::1')


@lru_cache(maxsize=8)
def _jaringan(daftar):
    hasil = []
    for item in daftar:
        item = item.strip()
        if item:
            hasil.append(ipaddress.ip_network(item, strict=False))
    return tuple(hasil)


def _proxy_tepercaya():
    daftar = getattr(settings, 'PROXY_TEPERCAYA', PROXY_TEPERCAYA_BAWAAN)
    if isinstance(daftar, str):
        daftar = daftar.split(',')
    return _jaringan(tuple(daftar))


def _normal(teks):
    """'203.0.113.7', '203.0.113.7:5123', '[2001:db8::1]:443' → alamat baku, atau None."""
    teks = (teks or '').strip()
    if not teks:
        return None
    if teks.startswith('[') and ']' in teks:
        teks = teks[1:teks.index(']')]
    elif teks.count(':') == 1 and '.' in teks:
        teks = teks.split(':', 1)[0]
    try:
        ip = ipaddress.ip_address(teks)
    except ValueError:
        return None
    # ::ffff:203.0.113.7 dicatat sebagai 203.0.113.7, supaya satu orang tidak
    # punya dua "IP" di log dan di penguncian axes.
    if ip.version == 6 and ip.ipv4_mapped:
        ip = ip.ipv4_mapped
    return str(ip)


def _tepercaya(ip):
    alamat = ipaddress.ip_address(ip)
    return any(alamat in jaringan for jaringan in _proxy_tepercaya())


def ip_klien(request):
    """IP pengguna sebenarnya untuk `request`, atau None kalau tidak diketahui."""
    meta = getattr(request, 'META', {}) or {}
    remote = _normal(meta.get('REMOTE_ADDR'))

    # REMOTE_ADDR kosong = gunicorn di-bind ke unix socket, yang hanya bisa
    # dijangkau proses di server ini sendiri (nginx) — sama tepercayanya
    # dengan 127.0.0.1.
    dari_proxy = remote is None or _tepercaya(remote)
    if not dari_proxy:
        # Tersambung langsung tanpa proxy kita: header apa pun dikarang
        # pengirimnya sendiri.
        return remote

    rantai = [b for b in (meta.get('HTTP_X_FORWARDED_FOR') or '').split(',') if b.strip()]
    for bagian in reversed(rantai):
        ip = _normal(bagian)
        if ip is None:
            # Proxy kita selalu menambahkan alamat yang sah; isian rusak berarti
            # kita sudah masuk ke bagian karangan pengirim — berhenti.
            break
        if not _tepercaya(ip):
            return ip
    return remote


def cek_ip(request):
    """
    /cek-ip/ — superuser saja: header yang benar-benar sampai ke Django dan IP
    yang disimpulkan darinya. Buka dari internet DAN dari jaringan kantor;
    `ip_klien` harus sama dengan IP publik / IP komputer Anda. Kalau yang
    keluar alamat proxy (mis. 172.17.x.x milik container cloudflared), tambahkan
    alamat itu ke PROXY_TEPERCAYA di .env lalu restart.
    """
    from django.http import Http404, JsonResponse

    if not (request.user.is_authenticated and request.user.is_superuser):
        raise Http404
    meta = request.META
    return JsonResponse({
        'ip_klien': ip_klien(request),
        'REMOTE_ADDR': meta.get('REMOTE_ADDR'),
        'X-Forwarded-For': meta.get('HTTP_X_FORWARDED_FOR'),
        'X-Real-IP': meta.get('HTTP_X_REAL_IP'),
        'CF-Connecting-IP': meta.get('HTTP_CF_CONNECTING_IP'),
        'PROXY_TEPERCAYA': [str(j) for j in _proxy_tepercaya()],
    }, json_dumps_params={'indent': 2})
