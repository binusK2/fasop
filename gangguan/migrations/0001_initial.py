from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('devices', '0014_device_status_operasi'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Gangguan',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nomor_gangguan', models.CharField(editable=False, max_length=30, unique=True, verbose_name='Nomor Gangguan')),
                ('status', models.CharField(
                    choices=[('open','Open'),('in_progress','In Progress'),('resolved','Resolved'),('closed','Closed')],
                    default='open', max_length=20, verbose_name='Status')),
                ('kategori', models.CharField(
                    choices=[('perangkat','Perangkat / Hardware'),('jaringan','Jaringan / Komunikasi'),
                             ('daya','Daya / Power'),('software','Software / Konfigurasi'),
                             ('eksternal','Faktor Eksternal'),('lainnya','Lainnya')],
                    default='perangkat', max_length=20, verbose_name='Kategori Gangguan')),
                ('tingkat_keparahan', models.CharField(
                    choices=[('kritis','Kritis'),('tinggi','Tinggi'),('sedang','Sedang'),('rendah','Rendah')],
                    default='sedang', max_length=10, verbose_name='Tingkat Keparahan')),
                ('tanggal_gangguan', models.DateTimeField(verbose_name='Tanggal & Jam Gangguan')),
                ('tanggal_resolved', models.DateTimeField(blank=True, null=True, verbose_name='Tanggal & Jam Resolved')),
                ('site', models.CharField(max_length=150, verbose_name='Site / Lokasi')),
                ('executive_summary', models.TextField(verbose_name='Executive Summary')),
                ('indikasi_gangguan', models.TextField(verbose_name='Indikasi Gangguan')),
                ('penyebab_gangguan', models.TextField(blank=True, verbose_name='Penyebab Gangguan')),
                ('dampak_gangguan', models.TextField(verbose_name='Dampak Gangguan')),
                ('tindak_lanjut', models.TextField(verbose_name='Tindak Lanjut')),
                ('catatan_penutupan', models.TextField(blank=True, verbose_name='Catatan Penutupan')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Dibuat Pada')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Diupdate Pada')),
                ('peralatan', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    to='devices.device', verbose_name='Peralatan Terdampak')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name='gangguan_dibuat', to=settings.AUTH_USER_MODEL, verbose_name='Dideklarasikan oleh')),
            ],
            options={'verbose_name': 'Gangguan', 'verbose_name_plural': 'Gangguan', 'ordering': ['-tanggal_gangguan']},
        ),
    ]
