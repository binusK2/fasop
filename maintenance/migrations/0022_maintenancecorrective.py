from django.db import migrations, models
import django.db.models.deletion
import maintenance.models


class Migration(migrations.Migration):

    dependencies = [
        ('maintenance', '0021_maintenance_catatan_am'),
        ('gangguan', '0005_gangguan_public_token'),
    ]

    operations = [
        migrations.CreateModel(
            name='MaintenanceCorrective',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('jenis_kerusakan', models.CharField(blank=True, max_length=20, verbose_name='Jenis Kerusakan',
                    choices=[('hardware','Hardware / Fisik'),('software','Software / Konfigurasi'),
                             ('power','Power / Catu Daya'),('komunikasi','Komunikasi / Jaringan'),
                             ('mekanik','Mekanik / Konektor'),('lainnya','Lainnya')])),
                ('deskripsi_masalah', models.TextField(verbose_name='Deskripsi Masalah / Kerusakan')),
                ('tindakan', models.TextField(verbose_name='Tindakan yang Dilakukan')),
                ('komponen_diganti', models.BooleanField(default=False, verbose_name='Ada Komponen Diganti?')),
                ('nama_komponen', models.CharField(blank=True, max_length=150, verbose_name='Nama Komponen')),
                ('kondisi_sebelum', models.CharField(blank=True, max_length=200, verbose_name='Kondisi Sebelum')),
                ('kondisi_sesudah', models.CharField(blank=True, max_length=200, verbose_name='Kondisi Sesudah')),
                ('durasi_jam', models.PositiveSmallIntegerField(null=True, blank=True, verbose_name='Durasi (jam)')),
                ('durasi_menit', models.PositiveSmallIntegerField(null=True, blank=True, verbose_name='Durasi (menit)')),
                ('status_perbaikan', models.CharField(max_length=25, default='selesai', verbose_name='Status Perbaikan',
                    choices=[('selesai','Selesai'),('perlu_tindaklanjut','Perlu Tindak Lanjut')])),
                ('foto_sebelum', models.ImageField(blank=True, null=True,
                    upload_to=maintenance.models.corrective_foto_upload, verbose_name='Foto Sebelum')),
                ('foto_sesudah', models.ImageField(blank=True, null=True,
                    upload_to=maintenance.models.corrective_foto_upload, verbose_name='Foto Sesudah')),
                ('maintenance', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='corrective_detail',
                    to='maintenance.maintenance',
                )),
                ('gangguan', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='corrective_maintenances',
                    to='gangguan.gangguan',
                    verbose_name='Terkait Gangguan',
                )),
            ],
            options={
                'verbose_name': 'Detail Corrective Maintenance',
                'verbose_name_plural': 'Detail Corrective Maintenance',
            },
        ),
    ]
