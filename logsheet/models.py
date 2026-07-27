"""
Logsheet Pembebanan — pengganti workbook Excel makro (LOGSHEET_MKS).

Konsep:
- Data ditarik dari MSSQL SCADA (server yang sama dengan OPSIS) tiap 30 menit
  oleh management command `collect_logsheet`, lalu disimpan sebagai NILAI per
  (titik, besaran, waktu) di sini — bukan lewat ribuan formula latch di Excel.
- Halaman web menampilkan data harian; tombol "Download Excel" mengisi nilai
  itu ke TEMPLATE (workbook asli, format identik) sehingga hasil unduhan sama
  persis dengan logsheet Excel yang lama, tanpa makro/beratnya.

Model:
- LogsheetTitik    : master titik ukur + pemetaan sumber MSSQL + posisi sel
                     export (sheet/baris) per besaran.
- LogsheetNilai    : nilai satu titik-besaran pada satu slot 30 menit (retensi
                     bergulir, mis. 1 bulan).
"""
from django.db import models


KATEGORI_CHOICES = [
    ('kit',       'Pembangkit (KIT)'),
    ('transmisi', 'Transmisi / Penghantar'),
    ('busbar',    'Busbar (Tegangan)'),
    ('trafo',     'Trafo / IBT'),
]

# Besaran yang direkam. Satu titik bisa punya beberapa besaran (mis. penghantar
# punya MW+MVAR+Amp); tiap besaran punya sheet & baris export sendiri.
BESARAN_CHOICES = [
    ('mw',   'Daya Aktif (MW)'),
    ('mvar', 'Daya Reaktif (MVAR)'),
    ('amp',  'Arus (A)'),
    ('volt', 'Tegangan (kV)'),
]


class LogsheetTitik(models.Model):
    """
    Master titik ukur + cara mengambilnya dari MSSQL + posisi di template Excel.

    Sumber MSSQL memakai pola query yang sama dengan makro lama:
        SELECT <kolom_mssql> FROM <tabel_mssql> WHERE <key_kolom_mssql>='<key_mssql>'
    (untuk KIT: tabel KIT_REALTIME, key_kolom='KIT', kolom=nama unit).
    """
    kategori   = models.CharField(max_length=12, choices=KATEGORI_CHOICES, db_index=True)
    besaran    = models.CharField(max_length=6, choices=BESARAN_CHOICES)
    key        = models.CharField(max_length=60, verbose_name='Kunci Titik',
                                  help_text='Identitas unik titik+besaran, mis. "KLKSM5-1:mw".')
    nama       = models.CharField(max_length=120, blank=True, verbose_name='Nama/Label')

    # ── Sumber data MSSQL ──
    mssql_tabel  = models.CharField(max_length=80, blank=True, verbose_name='Tabel MSSQL')
    mssql_kolom  = models.CharField(max_length=80, blank=True, verbose_name='Kolom MSSQL')
    mssql_keykol = models.CharField(max_length=80, blank=True, verbose_name='Kolom Kunci (WHERE)',
                                    help_text='Nama kolom untuk klausa WHERE, mis. KIT / ID / LINE.')
    mssql_key    = models.CharField(max_length=80, blank=True, verbose_name='Nilai Kunci',
                                    help_text='Nilai yang dicari pada kolom kunci.')
    faktor       = models.FloatField(default=1.0, verbose_name='Faktor Kali',
                                     help_text='Nilai MSSQL dikali faktor ini (skala/kalibrasi).')

    # ── Posisi di template export ──
    sheet      = models.CharField(max_length=40, blank=True, verbose_name='Sheet Export',
                                  help_text='Nama sheet di template, mis. KIT_MW.')
    baris      = models.PositiveIntegerField(null=True, blank=True, verbose_name='Baris Export',
                                             help_text='Nomor baris (1-based) tempat 48 kolom waktu diisi.')

    aktif      = models.BooleanField(default=True)

    class Meta:
        unique_together = ('key',)
        ordering = ['kategori', 'sheet', 'baris', 'key']
        verbose_name = 'Logsheet — Titik'
        verbose_name_plural = 'Logsheet — Titik'

    def __str__(self):
        return f'{self.key} ({self.get_besaran_display()})'


class LogsheetNilai(models.Model):
    """Nilai satu titik pada satu slot 30 menit."""
    titik   = models.ForeignKey(LogsheetTitik, on_delete=models.CASCADE, related_name='nilai', db_index=True)
    tanggal = models.DateField(db_index=True)
    slot    = models.PositiveSmallIntegerField(verbose_name='Slot 30-menit',
                                               help_text='0 = 00:30, 1 = 01:00, … 47 = 24:00.')
    waktu   = models.DateTimeField(help_text='Waktu pengambilan sebenarnya.')
    nilai   = models.FloatField(null=True)

    class Meta:
        unique_together = ('titik', 'tanggal', 'slot')
        indexes = [models.Index(fields=['tanggal', 'titik'])]
        ordering = ['-tanggal', 'titik', 'slot']
        verbose_name = 'Logsheet — Nilai'
        verbose_name_plural = 'Logsheet — Nilai'

    def __str__(self):
        return f'{self.titik.key} {self.tanggal} slot{self.slot} = {self.nilai}'
