from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import dokumentasi.models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('devices', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='SettingRele',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nomor', models.CharField(editable=False, max_length=25, unique=True, verbose_name='Nomor')),
                ('device', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='setting_rele', to='devices.device', verbose_name='Perangkat Rele')),
                ('judul', models.CharField(max_length=200, verbose_name='Judul')),
                ('tanggal', models.DateField(verbose_name='Tanggal')),
                ('versi', models.CharField(blank=True, max_length=50, verbose_name='Versi')),
                ('file_setting', models.FileField(blank=True, null=True, upload_to=dokumentasi.models.setting_file_upload, verbose_name='File Setting')),
                ('keterangan', models.TextField(blank=True, verbose_name='Keterangan')),
                ('checker', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='setting_rele_checked', to=settings.AUTH_USER_MODEL, verbose_name='Checker')),
                ('tanggal_cek', models.DateField(blank=True, null=True, verbose_name='Tanggal Cek')),
                ('status', models.CharField(choices=[('draft', 'Draft'), ('checked', 'Sudah Dicek')], default='draft', max_length=10, verbose_name='Status')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='setting_rele_dibuat', to=settings.AUTH_USER_MODEL, verbose_name='Dibuat Oleh')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Setting Rele',
                'verbose_name_plural': 'Setting Rele',
                'ordering': ['-tanggal', '-created_at'],
            },
        ),
        migrations.CreateModel(
            name='GambarDevice',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nomor', models.CharField(editable=False, max_length=25, unique=True, verbose_name='Nomor')),
                ('device', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='gambar_device', to='devices.device', verbose_name='Perangkat')),
                ('judul', models.CharField(max_length=200, verbose_name='Judul')),
                ('tipe', models.CharField(choices=[('wiring', 'Wiring Diagram'), ('single_line', 'Single Line Diagram'), ('skema', 'Skema Proteksi'), ('panel', 'Layout Panel'), ('lainnya', 'Lainnya')], default='wiring', max_length=20, verbose_name='Tipe Gambar')),
                ('tanggal', models.DateField(verbose_name='Tanggal')),
                ('versi', models.CharField(blank=True, max_length=50, verbose_name='Versi')),
                ('file_gambar', models.FileField(blank=True, null=True, upload_to=dokumentasi.models.gambar_upload, verbose_name='File Gambar')),
                ('keterangan', models.TextField(blank=True, verbose_name='Keterangan')),
                ('checker', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='gambar_device_checked', to=settings.AUTH_USER_MODEL, verbose_name='Checker')),
                ('tanggal_cek', models.DateField(blank=True, null=True, verbose_name='Tanggal Cek')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='gambar_device_dibuat', to=settings.AUTH_USER_MODEL, verbose_name='Dibuat Oleh')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Gambar / Wiring Diagram',
                'verbose_name_plural': 'Gambar / Wiring Diagram',
                'ordering': ['-tanggal', '-created_at'],
            },
        ),
    ]
