from django.db import models
from django.contrib.auth.models import User


MASTER_CHOICES = [
    ('spectrum',  'Spectrum'),
    ('survalent', 'Survalent'),
]
INPUT_TYPE_CHOICES = [
    ('soe',  'File SOE (Historical Messages)'),
    ('avrs', 'File AVRS (RTU Preprocessed)'),
    ('avrcd','File AVRCD (RCD Preprocessed)'),
]
CALC_TYPE_CHOICES = [
    ('rtu',  'RTU Availability'),
    ('rcd',  'RCD Success Rate'),
    ('both', 'RTU + RCD'),
]
STATUS_CHOICES = [
    ('pending',    'Menunggu'),
    ('processing', 'Memproses'),
    ('done',       'Selesai'),
    ('error',      'Error'),
]


class ScadaAvSession(models.Model):
    nama         = models.CharField(max_length=200, verbose_name='Nama Sesi')
    keterangan   = models.TextField(blank=True, verbose_name='Keterangan')
    periode_awal  = models.DateField(verbose_name='Periode Awal')
    periode_akhir = models.DateField(verbose_name='Periode Akhir')
    master        = models.CharField(max_length=20, choices=MASTER_CHOICES,    default='spectrum',  verbose_name='Sumber Data')
    input_type    = models.CharField(max_length=10, choices=INPUT_TYPE_CHOICES, default='soe',       verbose_name='Tipe File Input')
    calc_type     = models.CharField(max_length=10, choices=CALC_TYPE_CHOICES,  default='both',      verbose_name='Tipe Kalkulasi')
    status        = models.CharField(max_length=20, choices=STATUS_CHOICES,     default='pending')
    error_message  = models.TextField(blank=True)
    durasi_hitung  = models.FloatField(default=0, verbose_name='Durasi Kalkulasi (s)')
    dibuat_oleh    = models.ForeignKey(User, on_delete=models.SET_NULL, null=True,
                                       related_name='scada_av_sessions')
    dibuat_pada    = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-dibuat_pada']
        verbose_name = 'Sesi Kalkulasi SCADA AV'
        verbose_name_plural = 'Sesi Kalkulasi SCADA AV'

    def __str__(self):
        return f'{self.nama} ({self.periode_awal} s/d {self.periode_akhir})'

    @property
    def has_rtu(self):
        return self.calc_type in ('rtu', 'both')

    @property
    def has_rcd(self):
        return self.calc_type in ('rcd', 'both')

    @property
    def status_color(self):
        return {
            'pending':    'secondary',
            'processing': 'warning',
            'done':       'success',
            'error':      'danger',
        }.get(self.status, 'secondary')


class ScadaAvFile(models.Model):
    session     = models.ForeignKey(ScadaAvSession, on_delete=models.CASCADE, related_name='files')
    file        = models.FileField(upload_to='scada_av/uploads/%Y/%m/')
    filename    = models.CharField(max_length=255)
    ukuran      = models.PositiveBigIntegerField(default=0, verbose_name='Ukuran (bytes)')
    diunggah_pada = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.filename

    @property
    def ukuran_kb(self):
        return round(self.ukuran / 1024, 1)


# ── RTU Results ───────────────────────────────────────────────────────────────

class RtuAvResult(models.Model):
    """Per-RTU availability result."""
    session              = models.ForeignKey(ScadaAvSession, on_delete=models.CASCADE, related_name='rtu_results')
    rtu                  = models.CharField(max_length=100, verbose_name='RTU ID')
    long_name            = models.CharField(max_length=200, blank=True, verbose_name='Nama Lengkap')
    downtime_occurences  = models.IntegerField(default=0, verbose_name='Jumlah Downtime')
    total_downtime_s     = models.FloatField(default=0, verbose_name='Total Downtime (s)')
    rtu_downtime_s       = models.FloatField(default=0, verbose_name='RTU Downtime (s)')
    link_downtime_s      = models.FloatField(default=0, verbose_name='Link Downtime (s)')
    other_downtime_s     = models.FloatField(default=0, verbose_name='Other Downtime (s)')
    unclassified_dt_s    = models.FloatField(default=0, verbose_name='Unclassified Downtime (s)')
    time_range_s         = models.FloatField(default=0, verbose_name='Time Range (s)')
    rtu_availability     = models.FloatField(default=0, verbose_name='RTU Availability')
    link_availability    = models.FloatField(default=0, verbose_name='Link Availability')
    overall              = models.FloatField(default=0, verbose_name='Overall')

    class Meta:
        ordering = ['rtu']
        verbose_name = 'RTU Availability Result'

    def __str__(self):
        return f'{self.rtu} — {self.rtu_av_pct}%'

    @property
    def rtu_av_pct(self):
        return round(self.rtu_availability * 100, 2)

    @property
    def link_av_pct(self):
        return round(self.link_availability * 100, 2)

    @property
    def overall_pct(self):
        return round(self.overall * 100, 2)

    @property
    def total_downtime_hms(self):
        total = int(self.total_downtime_s)
        h, rem = divmod(total, 3600)
        m, s = divmod(rem, 60)
        return f'{h:02d}:{m:02d}:{s:02d}'

    @property
    def av_color(self):
        v = self.rtu_availability
        if v >= 0.99:  return 'success'
        if v >= 0.95:  return 'primary'
        if v >= 0.90:  return 'warning'
        return 'danger'


# ── RCD Results ───────────────────────────────────────────────────────────────

class RcdSummary(models.Model):
    """RCD success rate summary per session."""
    session             = models.OneToOneField(ScadaAvSession, on_delete=models.CASCADE, related_name='rcd_summary')
    total_count         = models.IntegerField(default=0, verbose_name='Total RC')
    total_valid         = models.IntegerField(default=0, verbose_name='Valid RC')
    total_success       = models.IntegerField(default=0, verbose_name='Sukses')
    total_failed        = models.IntegerField(default=0, verbose_name='Gagal')
    total_reps          = models.IntegerField(default=0, verbose_name='Repetisi')
    total_marked_unused = models.IntegerField(default=0, verbose_name='Unused')
    success_ratio       = models.FloatField(default=0, verbose_name='Success Rate')
    success_close_ratio = models.FloatField(default=0, verbose_name='Close Success Rate')
    success_open_ratio  = models.FloatField(default=0, verbose_name='Open Success Rate')

    class Meta:
        verbose_name = 'RCD Summary'

    @property
    def success_pct(self):
        return round(self.success_ratio * 100, 2)

    @property
    def success_close_pct(self):
        return round(self.success_close_ratio * 100, 2)

    @property
    def success_open_pct(self):
        return round(self.success_open_ratio * 100, 2)

    @property
    def sr_color(self):
        v = self.success_ratio
        if v >= 0.98:  return 'success'
        if v >= 0.95:  return 'primary'
        if v >= 0.90:  return 'warning'
        return 'danger'


class RcdBayResult(models.Model):
    """Per-bay RCD result."""
    session      = models.ForeignKey(ScadaAvSession, on_delete=models.CASCADE, related_name='rcd_bay_results')
    station      = models.CharField(max_length=100, verbose_name='Gardu Induk (B1)')
    bay_b2       = models.CharField(max_length=100, blank=True, verbose_name='B2')
    bay_b3       = models.CharField(max_length=200, verbose_name='Bay (B3)')
    occurences   = models.IntegerField(default=0, verbose_name='Jumlah RC')
    success      = models.IntegerField(default=0, verbose_name='Sukses')
    failed       = models.IntegerField(default=0, verbose_name='Gagal')
    success_rate = models.FloatField(default=0, verbose_name='Success Rate')
    open_success = models.IntegerField(default=0, verbose_name='Open Sukses')
    open_failed  = models.IntegerField(default=0, verbose_name='Open Gagal')
    close_success= models.IntegerField(default=0, verbose_name='Close Sukses')
    close_failed = models.IntegerField(default=0, verbose_name='Close Gagal')
    contribution = models.FloatField(default=0, verbose_name='Kontribusi')
    reduction    = models.FloatField(default=0, verbose_name='Reduksi')
    tagging      = models.CharField(max_length=10, blank=True, verbose_name='Tagging')

    class Meta:
        ordering = ['-reduction', '-failed']
        verbose_name = 'RCD Bay Result'

    @property
    def success_pct(self):
        return round(self.success_rate * 100, 2) if self.success_rate else (
            round(self.success / self.occurences * 100, 2) if self.occurences else 0
        )

    @property
    def contribution_pct(self):
        return round(self.contribution * 100, 2)

    @property
    def reduction_pct(self):
        return round(self.reduction * 100, 2)
