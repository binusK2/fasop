from django.db import migrations, models
import django.db.models.deletion
import devices.models


class Migration(migrations.Migration):

    dependencies = [
        ('auth', '0012_alter_user_first_name_max_length'),
        ('devices', '0016_devicelog'),
    ]

    operations = [
        migrations.CreateModel(
            name='DeviceEvent',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('tipe', models.CharField(max_length=20, verbose_name='Tipe Kejadian', choices=[
                    ('relokasi','Relokasi / Pindah Lokasi'),
                    ('penggantian','Penggantian Komponen'),
                    ('pembongkaran','Pembongkaran'),
                    ('pemasangan','Pemasangan Kembali'),
                    ('penambahan','Penambahan Komponen'),
                    ('modifikasi','Modifikasi Konfigurasi'),
                ])),
                ('tanggal', models.DateField(verbose_name='Tanggal Kejadian')),
                ('komponen', models.CharField(blank=True, max_length=150, verbose_name='Komponen')),
                ('nilai_lama', models.TextField(blank=True, verbose_name='Kondisi / Nilai Sebelumnya')),
                ('nilai_baru', models.TextField(blank=True, verbose_name='Kondisi / Nilai Sesudahnya')),
                ('lokasi_asal', models.CharField(blank=True, max_length=150, verbose_name='Lokasi Asal')),
                ('lokasi_tujuan', models.CharField(blank=True, max_length=150, verbose_name='Lokasi Tujuan')),
                ('catatan', models.TextField(blank=True, verbose_name='Catatan Tambahan')),
                ('foto', models.ImageField(blank=True, null=True,
                    upload_to=devices.models.device_event_foto_upload,
                    verbose_name='Foto Bukti')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('device', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='events', to='devices.device'
                )),
                ('dilakukan_oleh', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='device_events', to='auth.user',
                    verbose_name='Dicatat oleh'
                )),
            ],
            options={
                'verbose_name': 'Riwayat Kejadian Peralatan',
                'verbose_name_plural': 'Riwayat Kejadian Peralatan',
                'ordering': ['-tanggal', '-created_at'],
            },
        ),
    ]
