import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('inspection', '0006_inspectiontelecom_telecom_jenis'),
        ('devices', '0051_merge_main_otdr_chains'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='PengujianTelecom',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('tanggal', models.DateField(default=django.utils.timezone.now, verbose_name='Tanggal Pengujian')),
                ('lokasi', models.CharField(blank=True, max_length=100, verbose_name='Lokasi / GI')),
                ('catatan', models.TextField(blank=True, verbose_name='Catatan Umum')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('dibuat_oleh', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='pengujian_telecom', to=settings.AUTH_USER_MODEL, verbose_name='Dibuat Oleh')),
            ],
            options={
                'verbose_name': 'Pengujian Telekomunikasi',
                'verbose_name_plural': 'Pengujian Telekomunikasi',
                'ordering': ['-tanggal', '-created_at'],
            },
        ),
        migrations.CreateModel(
            name='PengujianTelecomItem',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('hasil', models.CharField(choices=[('normal', 'Normal'), ('tidak_normal', 'Tidak Normal')], default='normal', max_length=15, verbose_name='Hasil')),
                ('catatan', models.TextField(blank=True, verbose_name='Catatan')),
                ('device', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='pengujian_telecom_items', to='devices.device')),
                ('pengujian', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='items', to='inspection.pengujiantelecom')),
            ],
            options={
                'verbose_name': 'Item Pengujian Telekomunikasi',
                'ordering': ['device__jenis__name', 'device__nama'],
            },
        ),
    ]
