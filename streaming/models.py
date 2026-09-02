import secrets

from django.conf import settings
from django.contrib.auth.models import User
from django.db import models
from django.db.models import Q
from django.utils import timezone


def host_ezopen():
    """
    Host yang ditulis DI DALAM alamat `ezopen://` — bukan host API.

    Seluruh dokumentasi Ezviz mencontohkan `open.ys7.com`, dan itu memang
    benar untuk platform Tiongkok. Platform internasional MENOLAKNYA: server
    membalas `illegal parameter ezopen` (kode 10001) untuk host itu, dan hanya
    menerima `open.ezviz.com`. Terbukti di akun region Singapura milik UP2B —
    5 dari 5 kamera ditolak dengan open.ys7.com maupun host region-nya
    sendiri, dan diterima semua dengan open.ezviz.com.

    Pesan errornya tidak menyebut host, serial, maupun apa pun yang bisa
    ditindaklanjuti, jadi menebaknya mahal. Karena itu disimpulkan sendiri di
    sini dari platform yang dipakai, bukan dibebankan ke orang yang memasang.
    `EZVIZ_EZOPEN_HOST` tetap ada untuk menimpanya kalau suatu saat ada region
    yang tidak mengikuti pola ini — `manage.py cek_ezviz` yang menemukannya.
    """
    if settings.EZVIZ_EZOPEN_HOST:
        return settings.EZVIZ_EZOPEN_HOST
    return 'open.ys7.com' if 'ys7.com' in settings.EZVIZ_API_BASE else 'open.ezviz.com'


def _gen_token():
    return secrets.token_urlsafe(24)


# Sesi dianggap TIDAK sedang tersiar kalau penyiarnya tidak mengirim kabar
# selama sekian detik. Harus lebih besar dari interval kirim di broadcast.html
# (10 detik) supaya toleran jaringan lambat, tapi tetap cepat terasa: inilah
# yang membedakan "live beneran" dari "live tapi kotaknya hitam".
PUBLISHER_STALE_SECONDS = 30

# Setelah sekian detik tanpa penyiar, sesi diakhiri sendiri. Ini yang
# membereskan sesi hantu: teknisi tidak sengaja refresh/back/tab tertutup,
# lalu sesinya menggantung "Sedang Live" selamanya karena satu-satunya yang
# bisa mengakhiri adalah orang yang sudah pergi dari halamannya.
PUBLISHER_ABANDON_SECONDS = 300

# Ambang TERPISAH, dan jauh lebih longgar, untuk sesi yang belum pernah
# menyiar sekali pun. Teknisi lazim menekan "Mulai Live" dari kantor lalu
# berjalan dulu ke peralatannya; menutup sesinya setelah 5 menit berarti
# tombol "Mulai Kirim" ditolak MediaMTX (webhook auth mensyaratkan sesi masih
# live) tepat saat ia akhirnya siap. Yang dibereskan ambang ini cuma kasus
# jelas: sesi dibuat lalu tabnya ditutup dan tidak pernah disentuh lagi.
NEVER_STARTED_ABANDON_SECONDS = 1800


class KameraEzviz(models.Model):
    """
    Satu kamera CCTV Ezviz yang boleh dipakai sebagai sumber sesi live.

    Didaftarkan lewat site admin (Streaming → Kamera CCTV Ezviz) ATAU
    ditarik otomatis dari akun Ezviz lewat tombol "Sinkronkan dari Ezviz"
    di halaman daftar live — pola yang sama dengan Pembangkit/Titik EWS:
    menambah kamera tidak butuh migrasi maupun redeploy.

    Yang menentukan video mana yang diputar cuma `serial` + `channel`;
    `nama`/`lokasi` murni label untuk manusia, jadi hasil sinkronisasi dari
    Ezviz tidak pernah menimpa nama yang sudah diedit orang di sini (lihat
    streaming.ezviz.sinkron_kamera).
    """
    nama       = models.CharField(max_length=150, verbose_name='Nama Kamera')
    serial     = models.CharField(max_length=64, verbose_name='Serial Perangkat', help_text='Device serial di akun Ezviz, mis. BD3957004')
    channel    = models.PositiveSmallIntegerField(default=1, verbose_name='Channel', help_text='Nomor channel kamera. NVR punya banyak channel; kamera tunggal biasanya 1.')
    lokasi     = models.CharField(max_length=150, blank=True, verbose_name='Lokasi / Gardu Induk')
    hd         = models.BooleanField(default=True, verbose_name='Putar Kualitas HD', help_text='Nonaktifkan kalau jaringan lokasi lemah — kualitas turun, tapi lebih jarang buffering.')
    aktif      = models.BooleanField(default=True, verbose_name='Aktif', help_text='Hanya kamera aktif yang muncul di pilihan sumber saat memulai live.')
    keterangan = models.CharField(max_length=250, blank=True, verbose_name='Keterangan')

    # Diisi sinkronisasi dari API Ezviz — sekadar informasi di admin/daftar,
    # TIDAK dipakai untuk memblokir pemutaran: status di cloud kadang basi
    # beberapa menit, dan kamera yang dilaporkan offline masih sering bisa
    # ditarik streamnya.
    status_cloud     = models.CharField(max_length=20, blank=True, editable=False, verbose_name='Status di Cloud Ezviz')
    terakhir_sinkron = models.DateTimeField(null=True, blank=True, editable=False, verbose_name='Terakhir Disinkronkan')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['lokasi', 'nama']
        unique_together = ('serial', 'channel')
        verbose_name = 'Kamera CCTV Ezviz'
        verbose_name_plural = 'Kamera CCTV Ezviz'

    def __str__(self):
        if self.lokasi:
            return f'{self.nama} — {self.lokasi}'
        return self.nama

    def save(self, *args, **kwargs):
        # Serial dinormalkan di satu tempat, bukan saat merakit URL: dokumentasi
        # Ezviz mensyaratkan huruf pada serial ditulis KAPITAL, dan serial yang
        # tidak memenuhi itu ditolak server dengan "illegal parameter ezopen"
        # (kode 10001) — pesan yang sama sekali tidak menyebut serialnya.
        # Spasi ikut dibuang karena serial lazim disalin-tempel dari email/WA.
        if self.serial:
            self.serial = self.serial.strip().upper()
        # Channel 0 bukan nilai yang sah di Ezviz; kamera tunggal selalu 1.
        if not self.channel:
            self.channel = 1
        super().save(*args, **kwargs)

    @property
    def ezopen_url(self):
        """
        Alamat ezopen:// yang dimakan EZUIKitPlayer di browser.
        Format live: ezopen://<host>/{serial}/{channel}.live
        (varian HD menyisipkan ".hd" sebelum ".live").

        Host-nya ditentukan `host_ezopen()` (lihat catatan panjang di sana —
        open.ys7.com untuk platform Tiongkok, open.ezviz.com untuk yang lain).
        Ini BUKAN host API; region API ditentukan terpisah lewat areaDomain
        (lihat streaming.ezviz.domain_aktif).
        """
        mutu = 'hd.live' if self.hd else 'live'
        return f'ezopen://{host_ezopen()}/{self.serial}/{self.channel}.{mutu}'

    @property
    def ezopen_url_sd(self):
        """
        Varian sub-stream (SD), apa pun setelan `hd` kamera ini.

        Dipakai Multi View. Tanpa cross-origin isolation, browser tidak bisa
        memakai SharedArrayBuffer sehingga EZUIKit jatuh ke decoder perangkat
        lunak satu utas (terlihat di console sebagai "not support V3hard and
        V3Soft, switch V3 to V1"). Satu stream utama 2K/4MP saja sudah berat
        di jalur itu; sembilan sekaligus tidak akan pernah mengejar, dan
        gejalanya bukan error melainkan kotak yang memuat selamanya.

        Ini juga cara kerja dinding CCTV sungguhan: sub-stream di grid, stream
        utama baru saat satu kamera dibuka sendiri.
        """
        return f'ezopen://{host_ezopen()}/{self.serial}/{self.channel}.live'


class EzvizToken(models.Model):
    """
    Satu baris (pk=1) penampung accessToken akun Ezviz.

    Disimpan di DB, BUKAN di cache proses, karena FASOP jalan multi-worker
    gunicorn: dengan cache lokal tiap worker akan meminta token sendiri ke
    Ezviz dan gampang kena rate limit endpoint /api/lapp/token/get. Token
    berumur ~7 hari, jadi satu baris DB yang dibagi semua worker jauh lebih
    hemat daripada satu token per worker.
    """
    token      = models.CharField(max_length=255, blank=True)
    expire_at  = models.DateTimeField(null=True, blank=True)

    # `areaDomain` dari balasan /api/lapp/token/get. Dokumentasi Ezviz
    # menyebutnya "the open api domain name of the user's region, the
    # accessToken is valid only in this region" — jadi host inilah yang
    # benar untuk SEMUA panggilan berikutnya, dan juga yang harus dipakai
    # EZUIKit di browser sebagai env.domain.
    #
    # Menyimpannya berarti operator cukup mengarahkan EZVIZ_API_BASE ke
    # platform yang benar (Tiongkok vs internasional); region persisnya
    # ditentukan sendiri oleh Ezviz, tidak perlu ditebak manual.
    area_domain = models.CharField(max_length=200, blank=True, verbose_name='Domain Region dari Ezviz')

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Token Ezviz'
        verbose_name_plural = 'Token Ezviz'

    def __str__(self):
        return f'Token Ezviz (kedaluwarsa {self.expire_at:%d/%m/%Y %H:%M})' if self.expire_at else 'Token Ezviz (belum ada)'

    @property
    def masih_berlaku(self):
        # Margin 1 jam — jangan tunggu benar-benar kedaluwarsa, kalau tidak
        # sesi yang sedang diputar bisa mati di tengah jalan saat token habis.
        if not self.token or not self.expire_at:
            return False
        return self.expire_at > timezone.now() + timezone.timedelta(hours=1)


class LiveSession(models.Model):
    """
    Satu sesi live streaming pemeliharaan lapangan.

    Video utama dipublish oleh `teknisi` dan dibaca semua viewer (Teknisi/AM).
    Talkback audio (komunikasi 2 arah) hanya antara `teknisi` dan `pengawas` —
    dipublish oleh pengawas, dibaca hanya oleh teknisi. Semua akses ke media
    server (MediaMTX) divalidasi lewat token di bawah, dicek via webhook auth
    (lihat streaming.views.mediamtx_auth_webhook) — bukan lewat sesi Django,
    karena request WHIP/WHEP dikirim langsung oleh browser ke MediaMTX.
    """
    STATUS_CHOICES = (
        ('live',  'Live'),
        ('ended', 'Selesai'),
    )

    # Dari mana videonya datang. Dua sumber ini menempuh jalur yang BERBEDA
    # total sampai ke mata penonton:
    #   perangkat — kamera HP/laptop teknisi → WHIP → MediaMTX → WHEP ke
    #               penonton; ikut direkam server (recording_path).
    #   ezviz     — kamera CCTV di cloud Ezviz; browser penonton menarik
    #               langsung dari Ezviz lewat EZUIKit, TIDAK lewat MediaMTX
    #               dan karena itu TIDAK direkam FASOP (rekamannya ada di
    #               cloud/SD card kamera itu sendiri).
    # Talkback pengawas tetap lewat MediaMTX untuk kedua sumber.
    SUMBER_CHOICES = (
        ('perangkat', 'Kamera HP / Laptop'),
        ('ezviz',     'Kamera CCTV Ezviz'),
    )

    teknisi      = models.ForeignKey(User, on_delete=models.CASCADE, related_name='live_sessions', verbose_name='Teknisi')
    pengawas     = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='live_sessions_pengawas', verbose_name='Pengawas (AM)')
    judul        = models.CharField(max_length=200, blank=True, verbose_name='Judul / Lokasi Pemeliharaan')
    sumber       = models.CharField(max_length=10, choices=SUMBER_CHOICES, default='perangkat', verbose_name='Sumber Video')
    kamera       = models.ForeignKey(
        'KameraEzviz', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='sesi', verbose_name='Kamera CCTV Ezviz',
        help_text='Hanya dipakai kalau sumber = Kamera CCTV Ezviz.',
    )

    # Token rahasia untuk otorisasi publish/read di MediaMTX — jangan pernah ditampilkan di UI publik
    stream_key   = models.CharField(max_length=64, unique=True, editable=False, verbose_name='Token Publish Video')
    pengawas_key = models.CharField(max_length=64, blank=True, editable=False, verbose_name='Token Publish Talkback')
    view_token   = models.CharField(max_length=64, unique=True, editable=False, verbose_name='Token Baca Video')

    status       = models.CharField(max_length=10, choices=STATUS_CHOICES, default='live')
    started_at   = models.DateTimeField(auto_now_add=True)
    ended_at     = models.DateTimeField(null=True, blank=True)

    # Kapan terakhir kali browser teknisi mengabarkan bahwa WHIP publish-nya
    # masih hidup (lihat streaming.views.publisher_heartbeat).
    #
    # `status` saja tidak cukup untuk tahu sebuah sesi benar-benar tersiar:
    # status hanya berubah kalau ADA YANG MENEKAN "Akhiri Live". Begitu
    # teknisi tidak sengaja me-refresh, menekan back, atau tabnya tertutup,
    # publish-nya mati tapi barisnya tetap 'live' — sesi tampil "Sedang Live"
    # ke semua orang padahal tidak ada apa-apa untuk ditonton, dan orang yang
    # bisa mengakhirinya sudah pergi dari halaman itu. Kolom inilah yang
    # membuat keadaan tersebut bisa dilihat (dan dibereskan sendiri).
    #
    # NULL = tidak sedang menyiar. Kosong sejak awal (sesi baru dibuat, belum
    # menekan Mulai Kirim) DAN dikosongkan lagi secara eksplisit saat teknisi
    # berhenti/menutup halaman, supaya statusnya berubah seketika alih-alih
    # menunggu PUBLISHER_STALE_SECONDS lewat.
    publisher_last_seen = models.DateTimeField(
        null=True, blank=True, editable=False, verbose_name='Penyiar Terakhir Terlihat',
    )

    # Path absolut file rekaman di disk (ditulis MediaMTX, didaftarkan lewat
    # webhook streaming.views.mediamtx_record_webhook). Kosong = belum/tidak
    # ada rekaman. Dihapus otomatis oleh manage.py purge_old_recordings
    # setelah STREAMING_RECORDING_RETENTION_DAYS hari sejak ended_at.
    recording_path = models.CharField(max_length=500, blank=True, editable=False, verbose_name='Path Rekaman')

    # Klip audio talkback pengawas — file TERPISAH dari recording_path di
    # atas (bukan digabung/di-mix jadi satu file dengan video). Pengawas
    # bisa join/aktifkan-matikan mic kapan saja setelah teknisi live, jadi
    # mixing real-time ke satu file video berisiko rekaman video utama
    # terpecah tiap kali mic pengawas toggle — direkam terpisah supaya
    # pipeline rekaman video (yang sudah stabil) tidak ikut berisiko.
    # Kosong = tidak ada pengawas/mic tidak pernah diaktifkan sesi ini.
    talkback_recording_path = models.CharField(max_length=500, blank=True, editable=False, verbose_name='Path Rekaman Audio Pengawas')

    class Meta:
        ordering = ['-started_at']
        verbose_name = 'Sesi Live Streaming'
        verbose_name_plural = 'Sesi Live Streaming'

    def __str__(self):
        nama = self.teknisi.get_full_name() or self.teknisi.username
        return f'{self.judul or "Live"} — {nama} ({self.get_status_display()})'

    def save(self, *args, **kwargs):
        if not self.stream_key:
            self.stream_key = _gen_token()
        if not self.view_token:
            self.view_token = _gen_token()
        super().save(*args, **kwargs)

    @property
    def is_live(self):
        return self.status == 'live'

    @property
    def siaran_aktif(self):
        """
        True kalau sesi ini benar-benar mengalirkan video SEKARANG.

        Beda dari `is_live` (yang cuma bilang sesinya belum diakhiri).
        Sesi Ezviz selalu dianggap tersiar: videonya datang dari cloud, tidak
        ada browser yang mem-publish, jadi tidak ada yang bisa "putus" di
        sisi FASOP.
        """
        if not self.is_live:
            return False
        if self.is_ezviz:
            return True
        if not self.publisher_last_seen:
            return False
        return self.publisher_last_seen >= timezone.now() - timezone.timedelta(seconds=PUBLISHER_STALE_SECONDS)

    @property
    def pernah_tersiar(self):
        """
        True kalau sesi ini pernah benar-benar mengirim video.

        Dipakai broadcast.html untuk membedakan "sesi baru, teknisi masih
        memilih kamera" dari "sesi yang tadi sudah jalan lalu halamannya
        ter-refresh" — hanya kasus kedua yang disambung ulang otomatis.
        """
        return self.publisher_last_seen is not None or bool(self.recording_path)

    @classmethod
    def akhiri_yang_terbengkalai(cls):
        """
        Akhiri sesi yang penyiarnya sudah lama menghilang. Dipanggil sambil
        lalu dari halaman daftar & API Multi View — sengaja BUKAN cron: kondisi
        ini hanya perlu benar saat ada yang melihat daftarnya, dan satu
        UPDATE murah jauh lebih sederhana daripada satu job terjadwal lagi.

        Sesi Ezviz dikecualikan: tidak ada penyiar yang bisa menghilang, dan
        kameranya memang masih mengalir walau tidak ada yang menonton.
        """
        sekarang = timezone.now()
        batas_putus = sekarang - timezone.timedelta(seconds=PUBLISHER_ABANDON_SECONDS)
        batas_diam = sekarang - timezone.timedelta(seconds=NEVER_STARTED_ABANDON_SECONDS)
        return (
            cls.objects
            .filter(status='live')
            .exclude(sumber='ezviz')
            .filter(
                # Pernah menyiar lalu hilang (cepat dibereskan), ATAU tidak
                # pernah menyiar sama sekali sejak dibuat (dibereskan jauh
                # lebih lambat — lihat catatan di NEVER_STARTED_ABANDON_SECONDS).
                Q(publisher_last_seen__lt=batas_putus)
                | Q(publisher_last_seen__isnull=True, started_at__lt=batas_diam)
            )
            .update(status='ended', ended_at=sekarang)
        )

    @property
    def is_ezviz(self):
        """True kalau video sesi ini datang dari cloud Ezviz, bukan dari MediaMTX."""
        return self.sumber == 'ezviz'

    @property
    def ezopen_url(self):
        return self.kamera.ezopen_url if self.kamera_id and self.kamera else ''

    @property
    def video_path(self):
        """Path MediaMTX untuk video utama: publish oleh teknisi, dibaca semua viewer."""
        return f'live-{self.stream_key}'

    @property
    def talkback_path(self):
        """Path MediaMTX untuk audio talkback: publish oleh pengawas, dibaca hanya teknisi."""
        return f'live-{self.stream_key}-talk'

    @property
    def has_recording(self):
        return bool(self.recording_path)

    @property
    def has_talkback_recording(self):
        return bool(self.talkback_recording_path)

    def assign_pengawas(self, user):
        self.pengawas = user
        self.pengawas_key = _gen_token()
        self.save(update_fields=['pengawas', 'pengawas_key'])

    def end(self):
        self.status = 'ended'
        self.ended_at = timezone.now()
        self.save(update_fields=['status', 'ended_at'])


class LiveViewerHeartbeat(models.Model):
    """
    Dipakai untuk hitung penonton aktif secara perkiraan — browser viewer
    (viewer.html/pengawas.html) kirim heartbeat berkala selama nonton.
    Baris ini dianggap "aktif" kalau last_seen dalam beberapa detik terakhir
    (lihat streaming.views.session_status) — tidak perlu event "berhenti
    nonton" eksplisit, cukup biarkan basi kalau tab ditutup.
    """
    session   = models.ForeignKey(LiveSession, on_delete=models.CASCADE, related_name='viewer_heartbeats')
    user      = models.ForeignKey(User, on_delete=models.CASCADE)
    last_seen = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('session', 'user')
        verbose_name = 'Heartbeat Penonton'
        verbose_name_plural = 'Heartbeat Penonton'
