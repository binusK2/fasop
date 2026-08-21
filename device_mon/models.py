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
# ═══════════════════════════════════════════════════════════════════════════
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

    zabbix_hostid = models.CharField(
        max_length=50, unique=True, verbose_name='Host ID Zabbix',
        help_text='Kolom "hostid" dari Zabbix API (angka, unik per host).',
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
    """
    nama = models.CharField(
        max_length=100, unique=True, verbose_name='Nama Grup',
        help_text='Contoh: VoIP Mks, CRS, ROIP, Router, VoIP Baubau, VoIP ICON+, VoIP Luwuk',
    )
    hosts = models.ManyToManyField(
        ZabbixHost, blank=True, related_name='manual_groups',
        verbose_name='Host yang tergabung',
        help_text='Pilih host Zabbix yang masuk grup ini. Satu host boleh masuk beberapa grup.',
    )
    urutan = models.PositiveIntegerField(default=0, verbose_name='Urutan Tampil')
    aktif = models.BooleanField(
        default=True, verbose_name='Aktif',
        help_text='Nonaktifkan untuk menyembunyikan grup dari dashboard tanpa menghapusnya.',
    )
    keterangan = models.TextField(blank=True, verbose_name='Keterangan')

    class Meta:
        ordering = ['urutan', 'nama']
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
