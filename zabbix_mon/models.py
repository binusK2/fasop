from django.db import models


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
    lokasi = models.CharField(max_length=150, blank=True, verbose_name='Lokasi / Gardu')
    urutan = models.PositiveIntegerField(default=0, verbose_name='Urutan Tampil')
    aktif = models.BooleanField(default=True, verbose_name='Aktif')

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
        ordering = ['urutan', 'nama']
        verbose_name = 'Host Zabbix'
        verbose_name_plural = 'Host Zabbix'

    def __str__(self):
        return self.nama or self.zabbix_host or self.zabbix_hostid

    @property
    def is_ok(self):
        return self.state == 'OK'

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
