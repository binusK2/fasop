from django.db import models

from device_mon.zabbix_api import SEVERITY_LABELS

# Pilihan severity untuk ambang blast WhatsApp host Zabbix — diturunkan dari
# SEVERITY_LABELS supaya tidak ada daftar kembar yang bisa melenceng kalau
# Zabbix menambah level baru.
SEVERITY_CHOICES = sorted(
    ((idx, label) for idx, label in SEVERITY_LABELS.items()),
    key=lambda x: int(x[0]),
)


class RTU(models.Model):
    """
    Master data RTU.
    Nama diambil otomatis dari kolom RTU di dbo.RTU_ALL_STATE saat
    collect_rtu pertama berjalan.
    """
    nama        = models.CharField(max_length=50, unique=True, verbose_name='Nama RTU')
    lokasi      = models.CharField(max_length=100, blank=True, verbose_name='Lokasi / Gardu')
    urutan      = models.PositiveIntegerField(default=0, verbose_name='Urutan Tampil')
    aktif       = models.BooleanField(default=True, verbose_name='Aktif')
    wa_alert    = models.BooleanField(
        default=True, verbose_name='Blast WhatsApp',
        help_text='Kirim Early Warning WA saat RTU ini DOWN/pulih. '
                  'Hilangkan centang untuk membisukan satu RTU tanpa menonaktifkannya '
                  'dari monitoring.',
    )

    # ── State terkini (diperbarui setiap collect_rtu) ──────────────────
    state       = models.CharField(max_length=10, default='UNKNOWN', verbose_name='State')
    # UP / DOWN / UNKNOWN
    state_sejak = models.DateTimeField(null=True, blank=True, verbose_name='State Sejak')
    # TIME dari RTU_ALL_STATE — kapan state ini mulai

    class Meta:
        ordering     = ['urutan', 'nama']
        verbose_name = 'RTU'
        verbose_name_plural = 'RTU'

    def __str__(self):
        return self.nama

    @property
    def is_up(self):
        return self.state == 'UP'

    @property
    def durasi_menit(self):
        """Menit RTU sudah berada di state saat ini."""
        if not self.state_sejak:
            return None
        from django.utils import timezone
        return max(0, int((timezone.now() - self.state_sejak).total_seconds() / 60))

    def durasi_str(self):
        """Format human-readable: '2j 15m' / '45m'."""
        menit = self.durasi_menit
        if menit is None:
            return '—'
        if menit < 60:
            return f'{menit}m'
        j, m = divmod(menit, 60)
        return f'{j}j {m}m' if m else f'{j}j'


class RTULog(models.Model):
    """
    Log setiap interval state RTU (UP / DOWN).
    Dibuat saat transisi state terdeteksi oleh collect_rtu.
    Availability dihitung dari tabel ini.
    Auto-purge: data > 1 tahun dihapus saat collect_rtu berjalan.
    """
    rtu          = models.ForeignKey(RTU, on_delete=models.CASCADE, related_name='logs')
    state        = models.CharField(max_length=10)               # UP / DOWN
    mulai        = models.DateTimeField(db_index=True)           # kapan state ini mulai
    selesai      = models.DateTimeField(null=True, blank=True)   # null = masih berlangsung
    durasi_menit = models.PositiveIntegerField(null=True, blank=True)  # diisi saat selesai

    class Meta:
        ordering  = ['-mulai']
        indexes   = [models.Index(fields=['rtu', '-mulai'])]
        verbose_name = 'Log State RTU'
        verbose_name_plural = 'Log State RTU'

    def __str__(self):
        dur = f' ({self.durasi_menit}m)' if self.durasi_menit is not None else ''
        return f'{self.rtu.nama} {self.state} @ {self.mulai:%Y-%m-%d %H:%M}{dur}'


class RTUAlertLog(models.Model):
    """
    Audit trail Early Warning WhatsApp.
    Satu baris per percobaan kirim notif (DOWN / pemulihan UP) ke grup WA
    via OpenWA. Berguna untuk melacak "kenapa notif tidak masuk".
    Dibuat oleh collect_rtu saat transisi state terdeteksi.
    """
    JENIS_CHOICES = [
        ('DOWN', 'RTU Down'),
        ('UP',   'RTU Pulih'),
    ]

    rtu        = models.ForeignKey(RTU, on_delete=models.CASCADE, related_name='alerts')
    jenis      = models.CharField(max_length=10, choices=JENIS_CHOICES)
    pesan      = models.TextField(verbose_name='Isi pesan')
    terkirim   = models.BooleanField(default=False, verbose_name='Terkirim')
    keterangan = models.CharField(max_length=255, blank=True,
                                  verbose_name='Keterangan / error')
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering  = ['-created_at']
        indexes   = [models.Index(fields=['rtu', '-created_at'],
                                  name='devmon_alert_rtu_created_idx')]
        verbose_name = 'Log Early Warning WA'
        verbose_name_plural = 'Log Early Warning WA'

    def __str__(self):
        status = 'OK' if self.terkirim else 'GAGAL'
        return f'{self.rtu.nama} {self.jenis} [{status}] @ {self.created_at:%Y-%m-%d %H:%M}'


# ═══════════════════════════════════════════════════════════════════════════
#  Zabbix — status host dipantau lewat Zabbix API (pull) + webhook (push).
#  Sengaja satu app dengan RTU di atas: keduanya "status peralatan realtime",
#  jadi tetap ketemu di satu tempat (Device Monitor) alih-alih tersebar ke
#  app terpisah per sumber data.
#
#  BISA LEBIH DARI SATU instansi Zabbix (ZabbixInstance) — mis. "Zabbix
#  Telkom" dan "Zabbix Prosis", masing-masing server Zabbix sendiri dengan
#  kredensial API, filter Host Group, token webhook, dan tujuan WA sendiri.
#  Pola yang sama dengan opsis.SumberKit: baris admin, bukan kode, yang
#  membedakan instansi — menambah instansi ketiga nanti tidak perlu migrasi
#  ataupun redeploy.
# ═══════════════════════════════════════════════════════════════════════════
class ZabbixInstance(models.Model):
    """
    Satu baris = satu server Zabbix yang dipantau dari FASOP.

    Baris pertama ("Zabbix Telkom") dibuat oleh migrasi data dengan SELURUH
    field kredensial dikosongkan — kosong berarti jatuh ke ZABBIX_API_* /
    ZABBIX_WEBHOOK_TOKEN di `.env` (lihat `*_efektif()` di bawah), jadi
    pemasangan yang sudah ada sebelum model ini dibuat tidak berubah
    perilakunya sama sekali. Instansi baru (mis. Prosis) mengisi field-field
    ini sendiri karena tidak ada instansi kedua di `.env` untuk difallback-kan
    ke — menambah env var per instansi akan mengembalikan "menambah instansi
    baru butuh redeploy", justru yang ingin dihindari.

    `kode` dipakai di URL (`/device-mon/zabbix/<kode>/...`) — slug pendek,
    bukan hashid, sama seperti nama Grup Host Zabbix di URL grup.
    """
    # Kode ini bertabrakan dengan segmen path lain di bawah /device-mon/zabbix/
    # (lihat device_mon/urls.py — alias path lama & literal 'host'/'group')
    # kalau dipakai sebagai kode instansi; ditolak di clean() supaya tidak ada
    # instansi yang URL dashboard-nya diam-diam direbut redirect/alias lama.
    KODE_TERPAKAI = {'webhook', 'gangguan', 'group', 'host', 'api'}

    kode = models.SlugField(
        max_length=30, unique=True, verbose_name='Kode',
        help_text='Dipakai di URL, mis. "telkom" -> /device-mon/zabbix/telkom/. '
                  'Huruf kecil, angka, atau strip.',
    )
    nama = models.CharField(
        max_length=80, verbose_name='Nama Tampilan',
        help_text='Ditampilkan di menu & judul halaman, mis. "Zabbix Telkom".',
    )
    urutan = models.PositiveIntegerField(default=0, verbose_name='Urutan Tampil')
    aktif = models.BooleanField(
        default=True, verbose_name='Aktif',
        help_text='Nonaktifkan untuk menyembunyikan dari sidebar dan melewati instansi '
                  'ini di sync_zabbix, tanpa menghapus datanya.',
    )

    # ── Koneksi Zabbix API (kosong = jatuh ke ZABBIX_API_* di .env) ────────
    api_url = models.CharField(max_length=255, blank=True, default='', verbose_name='URL API',
                               help_text='mis. http://zabbix.local/api_jsonrpc.php')
    api_token = models.CharField(max_length=255, blank=True, default='', verbose_name='API Token')
    api_user = models.CharField(max_length=100, blank=True, default='', verbose_name='Username')
    api_password = models.CharField(max_length=255, blank=True, default='', verbose_name='Password')
    api_timeout = models.PositiveIntegerField(null=True, blank=True, verbose_name='Timeout (detik)')
    host_groups = models.CharField(
        max_length=255, blank=True, default='', verbose_name='Filter Host Group',
        help_text='Opsional, pisahkan koma bila lebih dari satu. Kosong = semua host aktif '
                  'di server ini.',
    )

    # ── Webhook (push realtime) ─────────────────────────────────────────
    webhook_token = models.CharField(
        max_length=255, blank=True, default='', verbose_name='Token Webhook',
        help_text='Kosong = jatuh ke ZABBIX_WEBHOOK_TOKEN di .env. Isi sendiri kalau '
                  'instansi ini perlu token berbeda dari instansi lain.',
    )

    # ── Blast WhatsApp ──────────────────────────────────────────────────
    wa_chat_ids = models.CharField(
        max_length=255, blank=True, default='', verbose_name='Tujuan WA Default',
        help_text='chatId tujuan default untuk seluruh host instansi ini (pisahkan koma). '
                  'Kosong = jatuh ke WA_CHAT_IDS_ZABBIX lalu WA_CHAT_IDS di .env. Host bisa '
                  'menimpa lagi lewat kolom "Grup WA Khusus" miliknya sendiri.',
    )

    class Meta:
        ordering = ['urutan', 'nama']
        verbose_name = 'Instansi Zabbix'
        verbose_name_plural = 'Instansi Zabbix'

    def __str__(self):
        return self.nama

    def clean(self):
        from django.core.exceptions import ValidationError
        super().clean()
        if self.kode in self.KODE_TERPAKAI:
            raise ValidationError({
                'kode': f'"{self.kode}" dipakai untuk path lain di /device-mon/zabbix/ — pilih kode lain.',
            })

    def api_url_efektif(self):
        from django.conf import settings
        return (self.api_url or '').strip() or (getattr(settings, 'ZABBIX_API_URL', '') or '')

    def api_token_efektif(self):
        from django.conf import settings
        return (self.api_token or '').strip() or (getattr(settings, 'ZABBIX_API_TOKEN', '') or '')

    def api_user_efektif(self):
        from django.conf import settings
        return (self.api_user or '').strip() or (getattr(settings, 'ZABBIX_API_USER', '') or '')

    def api_password_efektif(self):
        from django.conf import settings
        return self.api_password or (getattr(settings, 'ZABBIX_API_PASSWORD', '') or '')

    def api_timeout_efektif(self):
        from django.conf import settings
        return self.api_timeout or getattr(settings, 'ZABBIX_API_TIMEOUT', 10)

    def host_groups_list(self):
        """Nama Host Group untuk filter get_hosts() — None berarti semua host."""
        raw = (self.host_groups or '').strip()
        if not raw:
            from django.conf import settings
            raw = getattr(settings, 'ZABBIX_HOST_GROUPS', '') or ''
        names = [g.strip() for g in raw.split(',') if g.strip()]
        return names or None

    def webhook_token_efektif(self):
        from django.conf import settings
        return (self.webhook_token or '').strip() or (getattr(settings, 'ZABBIX_WEBHOOK_TOKEN', '') or '')

    def wa_chat_ids_efektif(self):
        """chatId tujuan default instansi ini — kolom sendiri, else WA_CHAT_IDS_ZABBIX,
        else WA_CHAT_IDS. Urutan fallback sama dengan zbx_targets_default() di
        notifications.py (di sana untuk host tanpa instance yang eksplisit)."""
        raw = (self.wa_chat_ids or '').strip()
        if not raw:
            from django.conf import settings
            raw = (getattr(settings, 'WA_CHAT_IDS_ZABBIX', '') or '').strip()
            raw = raw or (getattr(settings, 'WA_CHAT_IDS', '') or '')
        return [c.strip() for c in raw.split(',') if c.strip()]

    def client(self):
        """ZabbixClient terkonfigurasi untuk instansi ini (lihat device_mon.zabbix_api)."""
        from device_mon.zabbix_api import ZabbixClient
        return ZabbixClient(
            url=self.api_url_efektif(),
            token=self.api_token_efektif(),
            user=self.api_user_efektif(),
            password=self.api_password_efektif(),
            timeout=self.api_timeout_efektif(),
        )

    @classmethod
    def ambil_default(cls):
        """
        Instansi bawaan untuk ZabbixHost/ZabbixGroup yang dibuat tanpa
        menyebutkan instansi (shell, tes lama) — dipakai sebagai `default`
        field FK `instance`, BUKAN aturan runtime yang dipakai dashboard
        (setiap host tetap harus menunjuk instansi sungguhan miliknya).
        Dibuat sebagai 'Zabbix Telkom' (kredensial kosong -> ikut .env) kalau
        belum ada satu pun baris, supaya pemasangan sebelum model ini ada
        tetap berperilaku sama.
        """
        obj = cls.objects.filter(kode='telkom').first()
        if obj is not None:
            return obj
        obj = cls.objects.order_by('pk').first()
        if obj is not None:
            return obj
        return cls.objects.create(kode='telkom', nama='Zabbix Telkom')


def _default_zabbix_instance_id():
    return ZabbixInstance.ambil_default().pk


class ZabbixHost(models.Model):
    """
    Master data host Zabbix yang dipantau dari FASOP.
    Dibuat otomatis oleh `sync_zabbix` (pull via Zabbix API) saat host baru
    ditemukan, atau bisa juga dibuat manual di Admin lalu diisi
    `zabbix_hostid` untuk dipetakan ke host yang sudah ada di Zabbix.
    """
    STATE_CHOICES = [
        ('OK',      'OK'),
        ('PROBLEM', 'Problem'),
        ('UNKNOWN', 'Unknown'),
    ]

    instance = models.ForeignKey(
        ZabbixInstance, on_delete=models.PROTECT, related_name='hosts',
        default=_default_zabbix_instance_id, verbose_name='Instansi Zabbix',
        help_text='Server Zabbix asal host ini (mis. Telkom / Prosis).',
    )
    zabbix_hostid = models.CharField(
        max_length=50, verbose_name='Host ID Zabbix',
        help_text='Kolom "hostid" dari Zabbix API — unik PER INSTANSI (dua server Zabbix '
                  'berbeda boleh memakai hostid yang sama untuk host yang berbeda).',
    )
    zabbix_host = models.CharField(
        max_length=150, blank=True, verbose_name='Technical Name',
        help_text='Kolom "host" (nama teknis) dari Zabbix.',
    )
    nama = models.CharField(
        max_length=150, verbose_name='Nama Tampilan',
        help_text='Diambil dari "name" (visible name) Zabbix saat sync pertama; bisa diubah manual.',
    )
    device = models.ForeignKey(
        'devices.Device', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='zabbix_hosts', verbose_name='Perangkat FASOP',
        help_text='Opsional — hubungkan ke data aset FASOP yang sesuai.',
    )
    lokasi = models.ForeignKey(
        'devices.SiteLocation', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='zabbix_hosts', verbose_name='Lokasi / Gardu',
        help_text='Dari master data Lokasi Site FASOP (devices.SiteLocation) — supaya penamaan '
                   'lokasi konsisten dengan Device dan halaman lain, bukan diketik bebas.',
    )
    groups = models.CharField(
        max_length=255, blank=True, verbose_name='Grup Zabbix',
        help_text='Host Group Zabbix tempat host ini terdaftar (dipisah koma bila lebih dari '
                   'satu), diperbarui otomatis oleh sync_zabbix. Dipakai untuk mengelompokkan '
                   'tampilan per grup (VoIP Mks, CRS, ROIP, Router, dst — lihat ZABBIX_HOST_GROUPS).',
    )
    urutan = models.PositiveIntegerField(default=0, verbose_name='Urutan Tampil')
    aktif = models.BooleanField(default=True, verbose_name='Aktif')

    # ── Early Warning WhatsApp (per host, opsional) ────────────────────
    # Default mati: host baru hasil sync_zabbix tidak boleh langsung
    # membanjiri grup WA. Operator yang memilih host mana yang layak
    # di-blast lewat Admin (mis. VoIP Makassar).
    wa_alert = models.BooleanField(
        default=False, verbose_name='Blast WhatsApp',
        help_text='Centang agar transisi PROBLEM/pulih host ini dikirim ke grup WhatsApp '
                  'lewat OpenWA. Butuh WA_ALERT_ENABLED=True di .env.',
    )
    wa_min_severity = models.CharField(
        max_length=1, choices=SEVERITY_CHOICES, default='3',
        verbose_name='Severity Minimum',
        help_text='Blast PROBLEM hanya dikirim bila severity-nya minimal ini. '
                  'Naikkan kalau grup terlalu berisik.',
    )
    wa_chat_ids = models.CharField(
        max_length=255, blank=True, verbose_name='Grup WA Khusus',
        help_text='Opsional — chatId tujuan khusus host ini (pisahkan koma, grup berakhiran '
                  '"@g.us"). Kosongkan untuk memakai WA_CHAT_IDS_ZABBIX dari .env.',
    )

    # ── State terkini (diperbarui oleh sync_zabbix / webhook) ──────────
    state = models.CharField(max_length=10, choices=STATE_CHOICES, default='UNKNOWN')
    severity = models.CharField(max_length=30, blank=True, verbose_name='Severity Tertinggi')
    problem_name = models.CharField(max_length=255, blank=True, verbose_name='Problem Aktif')
    state_sejak = models.DateTimeField(null=True, blank=True, verbose_name='State Sejak')
    last_synced_at = models.DateTimeField(
        null=True, blank=True, verbose_name='Sinkron Terakhir',
        help_text='Kapan sync_zabbix terakhir berhasil membaca host ini dari Zabbix API.',
    )

    class Meta:
        # 'pk' di akhir sebagai tie-breaker — beda dengan RTU.nama (unique=True),
        # ZabbixHost.nama BUKAN unique (bisa saja dua host share nama sama di
        # Zabbix), jadi ['urutan', 'nama'] saja tidak dijamin deterministik dan
        # memicu UnorderedObjectListWarning Django admin saat list_editable dipakai.
        ordering = ['urutan', 'nama', 'pk']
        # hostid unik PER INSTANSI, bukan global — dua server Zabbix berbeda
        # boleh saja kebetulan memakai hostid yang sama untuk host lain.
        unique_together = [('instance', 'zabbix_hostid')]
        verbose_name = 'Host Zabbix'
        verbose_name_plural = 'Host Zabbix'

    def __str__(self):
        return self.nama or self.zabbix_host or self.zabbix_hostid

    @property
    def is_ok(self):
        return self.state == 'OK'

    @property
    def group_list(self):
        return [g.strip() for g in (self.groups or '').split(',') if g.strip()]

    @property
    def durasi_menit(self):
        if not self.state_sejak:
            return None
        from django.utils import timezone
        return max(0, int((timezone.now() - self.state_sejak).total_seconds() / 60))

    def durasi_str(self):
        menit = self.durasi_menit
        if menit is None:
            return '—'
        if menit < 60:
            return f'{menit}m'
        j, m = divmod(menit, 60)
        return f'{j}j {m}m' if m else f'{j}j'


class ZabbixEventLog(models.Model):
    """
    Log setiap interval state host (OK / PROBLEM).
    Dibuat saat transisi state terdeteksi oleh sync_zabbix (pull API) atau
    oleh webhook Zabbix Action (push realtime) — lihat kolom `source`.
    """
    SOURCE_CHOICES = [
        ('api',     'Zabbix API (pull)'),
        ('webhook', 'Zabbix Webhook (push)'),
    ]

    host = models.ForeignKey(ZabbixHost, on_delete=models.CASCADE, related_name='logs')
    state = models.CharField(max_length=10, choices=ZabbixHost.STATE_CHOICES)
    severity = models.CharField(max_length=30, blank=True)
    problem_name = models.CharField(max_length=255, blank=True)
    zabbix_eventid = models.CharField(
        max_length=50, blank=True, db_index=True,
        help_text='Kolom "eventid" Zabbix — dipakai untuk mencegah duplikasi transisi '
                   'antara sync_zabbix dan webhook.',
    )
    source = models.CharField(max_length=10, choices=SOURCE_CHOICES, default='api')
    mulai = models.DateTimeField(db_index=True)
    selesai = models.DateTimeField(null=True, blank=True)
    durasi_menit = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        ordering = ['-mulai']
        indexes = [models.Index(fields=['host', '-mulai'])]
        verbose_name = 'Log State Host Zabbix'
        verbose_name_plural = 'Log State Host Zabbix'

    def __str__(self):
        dur = f' ({self.durasi_menit}m)' if self.durasi_menit is not None else ''
        return f'{self.host.nama} {self.state} @ {self.mulai:%Y-%m-%d %H:%M}{dur}'


class ZabbixWebhookLog(models.Model):
    """
    Audit trail setiap request masuk ke endpoint webhook Zabbix.
    Endpoint ini ter-ekspos ke jaringan Zabbix server, jadi setiap
    percobaan (berhasil maupun ditolak/token salah/host tak dikenal)
    dicatat di sini untuk memudahkan debug konfigurasi Action/Media Type
    di sisi Zabbix.
    """
    received_at = models.DateTimeField(auto_now_add=True, db_index=True)
    ok = models.BooleanField(default=False)
    instance = models.ForeignKey(
        ZabbixInstance, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='webhook_logs', verbose_name='Instansi Zabbix',
        help_text='Instansi yang dituju URL webhook-nya — bisa kosong bila kode instansi '
                  'di URL tidak dikenali (lihat Keterangan).',
    )
    host = models.ForeignKey(
        ZabbixHost, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='webhook_logs',
    )
    keterangan = models.CharField(max_length=255, blank=True)
    payload = models.TextField(blank=True, verbose_name='Body JSON diterima')

    class Meta:
        ordering = ['-received_at']
        verbose_name = 'Log Webhook Zabbix'
        verbose_name_plural = 'Log Webhook Zabbix'

    def __str__(self):
        status = 'OK' if self.ok else 'GAGAL'
        who = self.host.nama if self.host else '?'
        return f'[{status}] {who} @ {self.received_at:%Y-%m-%d %H:%M}'


class ZabbixGroup(models.Model):
    """
    Grup manual host Zabbix — dikelola sendiri lewat Django Admin, TIDAK
    pernah disentuh `sync_zabbix`.

    Beda dengan field `ZabbixHost.groups` (Host Group dari sisi Zabbix) yang
    selalu ditimpa ulang tiap sync: grup di sini murni milik FASOP, jadi
    pengelompokan tampilan dashboard bisa disusun bebas tanpa harus ikut
    struktur Host Group di Zabbix (dan tidak hilang saat sync berikutnya).

    Milik satu instansi (`instance`) — grup "Router" di Zabbix Telkom dan
    "Router" di Zabbix Prosis adalah dua baris terpisah, boleh berbagi nama.
    """
    instance = models.ForeignKey(
        ZabbixInstance, on_delete=models.PROTECT, related_name='groups',
        default=_default_zabbix_instance_id, verbose_name='Instansi Zabbix',
    )
    nama = models.CharField(
        max_length=100, verbose_name='Nama Grup',
        help_text='Contoh: VoIP Mks, CRS, ROIP, Router, VoIP Baubau, VoIP ICON+, VoIP Luwuk',
    )
    hosts = models.ManyToManyField(
        ZabbixHost, blank=True, related_name='manual_groups',
        verbose_name='Host yang tergabung',
        help_text='Pilih host Zabbix yang masuk grup ini. Satu host boleh masuk beberapa grup. '
                  'Pilih host dari instansi Zabbix yang sama dengan grup ini.',
    )
    urutan = models.PositiveIntegerField(default=0, verbose_name='Urutan Tampil')
    aktif = models.BooleanField(
        default=True, verbose_name='Aktif',
        help_text='Nonaktifkan untuk menyembunyikan grup dari dashboard tanpa menghapusnya.',
    )
    keterangan = models.TextField(blank=True, verbose_name='Keterangan')

    class Meta:
        ordering = ['urutan', 'nama']
        unique_together = [('instance', 'nama')]
        verbose_name = 'Grup Host Zabbix'
        verbose_name_plural = 'Grup Host Zabbix'

    def __str__(self):
        return self.nama


class ZabbixAlertLog(models.Model):
    """
    Audit trail blast WhatsApp untuk host Zabbix.
    Satu baris per transisi yang *dipertimbangkan* untuk dikirim — termasuk
    yang sengaja dilewati (severity di bawah ambang, tujuan belum diisi),
    supaya pertanyaan "kenapa notif tidak masuk" bisa dijawab dari Admin
    tanpa membaca log server. Sepadan dengan RTUAlertLog di atas.
    """
    JENIS_CHOICES = [
        ('PROBLEM', 'Problem'),
        ('OK',      'Pulih'),
    ]

    host       = models.ForeignKey(ZabbixHost, on_delete=models.CASCADE, related_name='alerts')
    jenis      = models.CharField(max_length=10, choices=JENIS_CHOICES)
    pesan      = models.TextField(verbose_name='Isi pesan')
    terkirim   = models.BooleanField(default=False, verbose_name='Terkirim')
    keterangan = models.CharField(max_length=255, blank=True,
                                  verbose_name='Keterangan / error')
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['host', '-created_at'],
                                name='zbx_alert_host_created_idx')]
        verbose_name = 'Log Blast WA Zabbix'
        verbose_name_plural = 'Log Blast WA Zabbix'

    def __str__(self):
        status = 'OK' if self.terkirim else 'GAGAL'
        return f'{self.host.nama} {self.jenis} [{status}] @ {self.created_at:%Y-%m-%d %H:%M}'
