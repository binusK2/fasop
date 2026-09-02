"""streaming/ezviz.py — klien Ezviz Open Platform (open.ys7.com).

SATU-SATUNYA tempat FASOP berbicara HTTP ke cloud Ezviz. Kalau nanti akun
dipindah ke region lain atau endpointnya berubah, ubah di sini saja —
jangan menambah pemanggil `requests` kedua di views/template.

Fitur yang dilayani modul ini cuma dua:
  1. Mengambil `accessToken` akun (dipakai EZUIKit di browser penonton).
  2. Menarik daftar kamera akun untuk mengisi `KameraEzviz`.

Video ITU SENDIRI tidak pernah lewat server FASOP: browser penonton
menariknya langsung dari cloud Ezviz lewat EZUIKit. Jadi kalau kamera
gagal tampil, urutan pemeriksaannya adalah token (dari sini) dulu, baru
jaringan penonton ke open.ys7.com — bukan MediaMTX.
"""
import datetime
import logging

import requests
from django.conf import settings
from django.utils import timezone

from .models import EzvizToken, konfigurasi_ezviz

logger = logging.getLogger(__name__)

# Token Ezviz punya masa berlaku ~7 hari. Kalau respons tidak menyertakan
# expireTime (pernah terjadi di beberapa region), pakai umur konservatif ini
# supaya token tetap disegarkan berkala alih-alih dianggap abadi.
UMUR_TOKEN_CADANGAN_JAM = 24

# Kode error Ezviz yang artinya "token tidak berlaku lagi" — satu-satunya
# kondisi yang layak di-retry otomatis dengan token baru. 10001 SENGAJA tidak
# di sini: dokumentasi Ezviz menyebutnya "the parameter is empty or incorrect
# format", jadi mengulanginya dengan token baru cuma membakar satu permintaan
# token dan menyembunyikan bug parameter yang sebenarnya.
KODE_TOKEN_BASI = ('10002',)

# Kode error yang penyebab sebenarnya hampir selalu BUKAN yang tertulis di
# pesannya. Pesan asli Ezviz juga datang dalam bahasa yang berbeda tergantung
# host (Mandarin di open.ys7.com, Inggris di host luar Tiongkok), jadi tidak
# bisa diandalkan sendirian oleh orang yang membaca layar FASOP.
PETUNJUK_KODE = {
    '10017': (
        'appKey hanya berlaku di platform tempat ia dibuat, jadi ini hampir selalu '
        'salah region — bukan salah ketik. Setel EZVIZ_API_BASE ke host region akun '
        'Anda (mis. https://isgpopen.ezvizlife.com untuk Singapura); bawaannya '
        'https://open.ys7.com yang merupakan platform Tiongkok dengan akun terpisah.'
    ),
}


class EzvizError(Exception):
    """Kegagalan memanggil API Ezviz. `kode` = kode error dari Ezviz kalau ada."""

    def __init__(self, pesan, kode=''):
        super().__init__(pesan)
        self.kode = kode


def terkonfigurasi():
    """False = appKey/appSecret belum diisi, fitur sumber Ezviz dimatikan total."""
    konf = konfigurasi_ezviz()
    return bool(konf.app_key and konf.app_secret)


def _url(path, base=None):
    return (base or konfigurasi_ezviz().api_base).rstrip('/') + path


def domain_aktif():
    """
    Host API yang benar untuk akun ini.

    /api/lapp/token/get mengembalikan `areaDomain` — menurut dokumentasi
    Ezviz, host region tempat accessToken itu SATU-SATUNYA berlaku. Memakai
    nilai itu menghapus satu sumber kesalahan yang mahal: EZVIZ_API_BASE yang
    diisi setengah benar (mis. host global sementara akunnya di Singapura)
    membuat token berhasil diambil tapi setiap panggilan sesudahnya ditolak.

    Jatuh kembali ke EZVIZ_API_BASE selama token belum pernah diambil.
    """
    baris = EzvizToken.objects.filter(pk=1).first()
    if baris and baris.area_domain:
        return baris.area_domain
    return konfigurasi_ezviz().api_base


def _panggil(path, data, base=None):
    """
    POST form-encoded ke Ezviz dan kembalikan isi `data` dari responsnya.

    Ezviz SELALU membalas HTTP 200 walau operasinya gagal — status
    sebenarnya ada di field `code` ("200" = sukses). Jadi jangan pernah
    menyimpulkan sukses dari resp.ok saja.
    """
    host = (base or konfigurasi_ezviz().api_base).rstrip('/')
    try:
        resp = requests.post(_url(path, host), data=data, timeout=settings.EZVIZ_TIMEOUT)
    except requests.RequestException as e:
        raise EzvizError(f'Tidak bisa menghubungi cloud Ezviz di {host}: {e}') from e

    if resp.status_code != 200:
        raise EzvizError(f'Cloud Ezviz membalas HTTP {resp.status_code}')

    try:
        payload = resp.json()
    except ValueError as e:
        raise EzvizError('Balasan cloud Ezviz bukan JSON') from e

    kode = str(payload.get('code', ''))
    if kode != '200':
        pesan = payload.get('msg') or 'tanpa keterangan'
        # Sebut host-nya: sebagian besar kegagalan di sini adalah permintaan
        # yang benar dikirim ke platform region yang salah, dan itu mustahil
        # terlihat dari pesan Ezviz sendiri.
        keterangan = f'Ezviz ({host}) menolak permintaan ({kode}): {pesan}'
        petunjuk = PETUNJUK_KODE.get(kode)
        if petunjuk:
            keterangan += f' — {petunjuk}'
        raise EzvizError(keterangan, kode=kode)

    return payload.get('data')


def _minta_token_baru():
    konf = konfigurasi_ezviz()
    data = _panggil('/api/lapp/token/get', {
        'appKey': konf.app_key,
        'appSecret': konf.app_secret,
    }) or {}

    token = data.get('accessToken')
    if not token:
        raise EzvizError('Cloud Ezviz tidak mengembalikan accessToken')

    expire_ms = data.get('expireTime')
    if expire_ms:
        # expireTime = epoch milidetik.
        expire_at = datetime.datetime.fromtimestamp(int(expire_ms) / 1000, tz=datetime.timezone.utc)
    else:
        expire_at = timezone.now() + datetime.timedelta(hours=UMUR_TOKEN_CADANGAN_JAM)

    # areaDomain kosong di sebagian region/versi — kalau begitu, biarkan
    # nilai lama (atau EZVIZ_API_BASE) yang dipakai, jangan ditimpa string
    # kosong yang justru menghapus informasi yang sudah benar.
    area_domain = (data.get('areaDomain') or '').strip()
    nilai = {'token': token, 'expire_at': expire_at}
    if area_domain:
        nilai['area_domain'] = area_domain

    baris, _ = EzvizToken.objects.update_or_create(pk=1, defaults=nilai)
    logger.info(
        'Token Ezviz baru diambil, berlaku sampai %s, region %s',
        expire_at, baris.area_domain or konfigurasi_ezviz().api_base,
    )
    return baris.token


def ambil_access_token(paksa_baru=False):
    """
    accessToken akun Ezviz — dari baris DB kalau masih berlaku, kalau tidak
    minta baru ke Ezviz. Melempar EzvizError kalau gagal.

    `paksa_baru=True` dipakai saat Ezviz sendiri bilang token basi
    (lihat _dengan_token di bawah), bukan sebagai perilaku normal: minta
    token terlalu sering bisa kena rate limit endpoint /token/get.
    """
    if not terkonfigurasi():
        raise EzvizError(
            'appKey/appSecret Ezviz belum diisi — isi di Admin → Streaming → '
            'Pengaturan Ezviz, atau lewat EZVIZ_APP_KEY/EZVIZ_APP_SECRET di .env.'
        )

    if not paksa_baru:
        baris = EzvizToken.objects.filter(pk=1).first()
        if baris and baris.masih_berlaku:
            return baris.token

    return _minta_token_baru()


def _dengan_token(path, data=None):
    """
    Panggil endpoint yang butuh accessToken, dengan SATU kali coba ulang
    kalau Ezviz bilang tokennya basi — token bisa dicabut dari sisi Ezviz
    (mis. appSecret di-reset) sebelum expire_at yang kita simpan lewat.
    """
    payload = dict(data or {})
    payload['accessToken'] = ambil_access_token()
    # domain_aktif() dibaca SETELAH token diambil: permintaan token itulah
    # yang mengisi areaDomain untuk pertama kalinya.
    try:
        return _panggil(path, payload, base=domain_aktif())
    except EzvizError as e:
        if e.kode not in KODE_TOKEN_BASI:
            raise
        payload['accessToken'] = ambil_access_token(paksa_baru=True)
        return _panggil(path, payload, base=domain_aktif())


def _halaman_penuh(path, keterangan):
    """
    Tarik seluruh halaman sebuah endpoint list Ezviz (pageStart/pageSize).
    Ezviz membatasi pageSize maksimal 50 dan tidak punya mode "ambil semua".
    """
    hasil = []
    halaman = 0
    while True:
        data = _dengan_token(path, {'pageStart': halaman, 'pageSize': 50}) or []
        hasil.extend(data)
        if len(data) < 50:
            break
        halaman += 1
        if halaman > 40:  # 2000 kamera — jauh di atas kebutuhan, cegah loop tak berujung
            logger.warning('Daftar %s dari Ezviz melebihi 2000 baris, dipotong.', keterangan)
            break
    return hasil


def daftar_kamera_cloud():
    """
    Daftar channel kamera di akun Ezviz, sudah digabung dengan nama
    perangkatnya. Return list dict: {serial, channel, nama, status}.

    Dua endpoint dipakai karena masing-masing hanya tahu separuh cerita:
    /camera/list tahu channel + nama channel tapi tidak tahu nama
    perangkat; /device/list tahu nama perangkat tapi tidak memecah channel.
    Untuk NVR, satu perangkat = banyak channel, jadi channel HARUS datang
    dari /camera/list.
    """
    kamera = _halaman_penuh('/api/lapp/camera/list', 'kamera')

    nama_device = {}
    try:
        for d in _halaman_penuh('/api/lapp/device/list', 'perangkat'):
            if d.get('deviceSerial'):
                nama_device[d['deviceSerial']] = d.get('deviceName') or ''
    except EzvizError as e:
        # Nama perangkat cuma pemanis label — kalau endpoint ini gagal
        # (mis. sub-akun tanpa izin device/list), sinkronisasi tetap jalan
        # memakai nama channel saja.
        logger.warning('Gagal ambil nama perangkat dari Ezviz: %s', e)

    hasil = []
    for c in kamera:
        serial = (c.get('deviceSerial') or '').strip().upper()
        if not serial:
            continue
        try:
            channel = int(c.get('channelNo') or 1)
        except (TypeError, ValueError):
            channel = 1
        nama_ch = (c.get('channelName') or '').strip()
        nama_dev = (nama_device.get(serial) or '').strip()
        if nama_dev and nama_ch and nama_dev != nama_ch:
            nama = f'{nama_dev} — {nama_ch}'
        else:
            nama = nama_ch or nama_dev or f'{serial}/{channel}'
        hasil.append({
            'serial': serial,
            'channel': channel,
            'nama': nama[:150],
            'status': 'online' if str(c.get('status', '')) == '1' else 'offline',
        })
    return hasil


def sinkron_kamera():
    """
    Cocokkan daftar kamera cloud ke tabel KameraEzviz.

    Aturan yang sengaja dipilih:
      - Kamera baru dibuat AKTIF, karena orang yang menekan tombol sinkron
        memang sedang menambah kamera untuk dipakai. (Beda dari ZabbixHost
        yang dibuat otomatis oleh cron tanpa ada yang memutuskan apa pun —
        di sana default senyap memang benar.)
      - Kamera yang sudah ada TIDAK ditimpa nama/lokasinya. Nama dari Ezviz
        biasanya bawaan pabrik ("C6N"), sedangkan yang berguna di FASOP
        adalah nama versi PLN yang diketik orang di admin.
      - Kamera yang hilang dari cloud TIDAK dihapus, cuma ditandai
        status_cloud='hilang' — menghapus barisnya akan memutus tautan sesi
        live lama yang menunjuk kamera itu.

    Return dict ringkasan untuk ditampilkan sebagai pesan ke pengguna.
    """
    from .models import KameraEzviz  # lokal: hindari import melingkar saat modul dimuat

    cloud = daftar_kamera_cloud()
    sekarang = timezone.now()
    dibuat = diperbarui = 0
    terlihat = set()

    for c in cloud:
        terlihat.add((c['serial'], c['channel']))
        obj = KameraEzviz.objects.filter(serial=c['serial'], channel=c['channel']).first()
        if obj is None:
            KameraEzviz.objects.create(
                nama=c['nama'], serial=c['serial'], channel=c['channel'],
                status_cloud=c['status'], terakhir_sinkron=sekarang,
            )
            dibuat += 1
        else:
            obj.status_cloud = c['status']
            obj.terakhir_sinkron = sekarang
            obj.save(update_fields=['status_cloud', 'terakhir_sinkron', 'updated_at'])
            diperbarui += 1

    hilang = 0
    for obj in KameraEzviz.objects.exclude(status_cloud='hilang'):
        if (obj.serial, obj.channel) not in terlihat:
            obj.status_cloud = 'hilang'
            obj.save(update_fields=['status_cloud', 'updated_at'])
            hilang += 1

    return {'dibuat': dibuat, 'diperbarui': diperbarui, 'hilang': hilang, 'total': len(cloud)}
