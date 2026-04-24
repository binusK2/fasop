from django.db import models


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
