from django.db import models


class SitePath1(models.Model):
    """
    Daftar PATH1 (site/pembangkit) yang pernah muncul di scd_c_point (OFDB), dengan
    flag aktif/tidak untuk menyaring titik mana yang ikut dihitung kinerjanya.
    Diisi/di-upsert otomatis oleh sync_kinerja_analog/sync_kinerja_digital saat
    menjumpai path1 baru (default aktif=True) -- tinggal di-nonaktifkan lewat admin
    kalau ada site lama/tidak relevan yang ikut ke-hitung.
    """
    path1 = models.CharField(max_length=100, unique=True, db_index=True)
    aktif = models.BooleanField(
        default=True,
        help_text='Kalau dicentang, semua titik dengan PATH1 ini ikut dihitung kinerjanya.'
    )
    keterangan = models.CharField(max_length=200, blank=True, default='')
    dibuat_pada = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['path1']
        verbose_name = 'Site (PATH1) Aktif/Tidak'
        verbose_name_plural = 'Site (PATH1) Aktif/Tidak'

    def __str__(self):
        return f"{self.path1} ({'Aktif' if self.aktif else 'Tidak Aktif'})"


class KinerjaHarianBase(models.Model):
    """
    Field bersama rekap harian kinerja titik ANALOG/DIGITAL.

    path1..path5 = kode mentah dari scd_c_point (path1 = station/B1, dipakai untuk
    grouping rekap per station seperti app up2bmakassar). b1..elem = versi terbaca
    dari pathXtext, dipakai untuk tampilan.

    `jenis` = nama INDUK point type di OFDB (TELEMETERING / TELESIGNAL / RTU /
    MASTER / TELEKOMUNIKASI) -- itu yang menentukan titik ini masuk halaman mana,
    sama seperti filter id_induk_pointtype di app up2bmakassar.
    """
    point_number = models.IntegerField(db_index=True)
    jenis = models.CharField(max_length=50, blank=True, default='', db_index=True)
    path1 = models.CharField(max_length=100, blank=True, default='')
    path2 = models.CharField(max_length=100, blank=True, default='')
    path3 = models.CharField(max_length=100, blank=True, default='')
    path4 = models.CharField(max_length=100, blank=True, default='')
    path5 = models.CharField(max_length=100, blank=True, default='')
    b1 = models.CharField(max_length=100, blank=True, default='')
    b2 = models.CharField(max_length=100, blank=True, default='')
    b3 = models.CharField(max_length=100, blank=True, default='')
    elem = models.CharField(max_length=100, blank=True, default='')
    tanggal = models.DateField(db_index=True)
    jumlah_up = models.IntegerField(default=0)
    uptime_detik = models.FloatField(default=0)
    alltime_detik = models.FloatField(default=0)
    performance = models.FloatField(default=0)  # persen, 0-100
    dihitung_pada = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True

    @property
    def downtime_detik(self):
        return max(self.alltime_detik - self.uptime_detik, 0)

    def __str__(self):
        return f'{self.point_number} - {self.tanggal} ({self.performance:.2f}%)'


class KinerjaAnalogHarian(KinerjaHarianBase):
    """
    Rekap harian kinerja (uptime) titik ANALOG = jenis TELEMETERING, dihitung dari
    histori transisi status di OFDB (dbup2bmakasar.scd_his_analog, dibaca read-only).

    Formula (portasi dari up2bmakassar deprecated/task/old/scd_kin_analog_harian.py):
    performance = total durasi kesimpulan='VALID' dalam 1 hari / total detik dalam 1 hari * 100
    """

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['point_number', 'tanggal'], name='uniq_kinerja_analog_harian')
        ]
        indexes = [
            models.Index(fields=['tanggal', 'point_number']),
            models.Index(fields=['jenis', 'tanggal'], name='up2b_kin_ana_jenis_tgl_idx'),
        ]
        verbose_name = 'Kinerja Analog Harian'
        verbose_name_plural = 'Kinerja Analog Harian'


class RemoteControl(models.Model):
    """
    Log RC (remote control) individual, diselesaikan (resolved BERHASIL/GAGAL) dari
    OFDB scd_his_rc (perintah) + scd_his_message (respons) -- dibaca read-only,
    hasil resolusinya disimpan di sini, TIDAK ditulis balik ke OFDB.

    ofdb_id_his_rc = id_his_rc di OFDB, dipakai sebagai kunci upsert idempotent.
    """
    ofdb_id_his_rc = models.IntegerField(unique=True, db_index=True)
    path1 = models.CharField(max_length=100, blank=True, default='')
    path2 = models.CharField(max_length=100, blank=True, default='')
    path3 = models.CharField(max_length=100, blank=True, default='')
    path4 = models.CharField(max_length=100, blank=True, default='')
    path5 = models.CharField(max_length=100, blank=True, default='')
    b1 = models.CharField(max_length=100, blank=True, default='')
    b2 = models.CharField(max_length=100, blank=True, default='')
    b3 = models.CharField(max_length=100, blank=True, default='')
    elem = models.CharField(max_length=100, blank=True, default='')
    operator = models.CharField(max_length=100, blank=True, default='')
    tanggal = models.DateField(db_index=True)
    datum_eksekusi = models.DateTimeField(null=True, blank=True)
    status_eksekusi = models.CharField(max_length=100, blank=True, default='')
    datum_respon = models.DateTimeField(null=True, blank=True)
    status_respon = models.CharField(max_length=100, blank=True, default='')  # BERHASIL / GAGAL
    dihitung_pada = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['tanggal']),
            models.Index(fields=['path1', 'path2', 'path3']),
        ]
        verbose_name = 'Remote Control (RC) Log'
        verbose_name_plural = 'Remote Control (RC) Log'

    def __str__(self):
        return f'{self.b1}/{self.b3}/{self.elem} - {self.tanggal} ({self.status_respon})'


class KinerjaDigitalHarian(KinerjaHarianBase):
    """
    Rekap harian kinerja (uptime) titik DIGITAL, dihitung dari histori transisi
    status di OFDB (dbup2bmakasar.scd_his_digital, dibaca read-only).

    Satu tabel menampung semua jenis titik digital (TELESIGNAL, RTU, MASTER,
    TELEKOMUNIKASI) -- sama seperti scd_kin_digital_bulan di up2bmakassar yang
    dipakai bersama oleh halaman Telesignal/RTU/Master Station. Halaman FASOP
    menyaringnya lewat field `jenis`.
    """

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['point_number', 'tanggal'], name='uniq_kinerja_digital_harian')
        ]
        indexes = [
            models.Index(fields=['tanggal', 'point_number']),
            models.Index(fields=['jenis', 'tanggal'], name='up2b_kin_dig_jenis_tgl_idx'),
        ]
        verbose_name = 'Kinerja Digital Harian'
        verbose_name_plural = 'Kinerja Digital Harian'
