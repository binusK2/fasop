from django.db import models
from devices.models import Device


class HISnapshot(models.Model):
    """
    Snapshot Health Index per peralatan, disimpan otomatis sekali per bulan.
    """
    device      = models.ForeignKey(Device, on_delete=models.CASCADE, related_name='hi_snapshots')
    score       = models.IntegerField(verbose_name='Skor HI')
    kategori    = models.CharField(max_length=20, verbose_name='Kategori')
    breakdown   = models.JSONField(default=list, verbose_name='Breakdown Faktor')
    bulan       = models.PositiveSmallIntegerField(verbose_name='Bulan')
    tahun       = models.PositiveSmallIntegerField(verbose_name='Tahun')
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = 'Snapshot Health Index'
        verbose_name_plural = 'Snapshot Health Index'
        unique_together     = ('device', 'bulan', 'tahun')
        ordering            = ['-tahun', '-bulan']

    def __str__(self):
        return f'{self.device.nama} — {self.bulan:02d}/{self.tahun} — {self.score}'

    @property
    def label_bulan(self):
        import calendar
        return f"{calendar.month_abbr[self.bulan]} {self.tahun}"


class KonfigurasiHI(models.Model):
    """
    Konfigurasi bobot tiap faktor Health Index.
    Satu record per faktor. Bisa diubah dari halaman Setting HI.
    """
    faktor_key  = models.CharField(max_length=50, unique=True, verbose_name='Kode Faktor')
    nama        = models.CharField(max_length=100, verbose_name='Nama Faktor')
    icon        = models.CharField(max_length=50, default='bi-circle', verbose_name='Icon')
    bobot_maks  = models.IntegerField(verbose_name='Bobot Maks (negatif)',
                                      help_text='Nilai negatif, contoh: -25')
    aktif       = models.BooleanField(default=True, verbose_name='Aktif')
    urutan      = models.PositiveSmallIntegerField(default=0, verbose_name='Urutan Tampil')
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = 'Konfigurasi Health Index'
        verbose_name_plural = 'Konfigurasi Health Index'
        ordering            = ['urutan', 'faktor_key']

    def __str__(self):
        status = '✓' if self.aktif else '✗'
        return f'[{status}] {self.nama} (bobot: {self.bobot_maks})'

    @classmethod
    def get_or_init(cls):
        """
        Ambil semua konfigurasi. Jika belum ada di DB,
        inisialisasi dari DEFAULT_BOBOT di registry.
        """
        from health_index.registry import DEFAULT_BOBOT, DEFAULT_NAMA, DEFAULT_ICON, FACTOR_CLASSES

        existing_keys = set(cls.objects.values_list('faktor_key', flat=True))
        to_create = []

        for i, factor_cls in enumerate(FACTOR_CLASSES):
            key = factor_cls.key
            if key not in existing_keys:
                to_create.append(cls(
                    faktor_key = key,
                    nama       = DEFAULT_NAMA.get(key, key),
                    icon       = DEFAULT_ICON.get(key, 'bi-circle'),
                    bobot_maks = DEFAULT_BOBOT.get(key, -10),
                    aktif      = True,
                    urutan     = i,
                ))

        if to_create:
            cls.objects.bulk_create(to_create)

        return cls.objects.all()

