"""
Migration: Tambah field layanan_icon (FK ke devices.Icon) pada model Gangguan
Jalankan: python manage.py migrate gangguan
"""
# Generated manually — tambahkan setelah 0008_gangguan_komponen_rusak_and_more

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('devices', '0023_deviceevent_komponen_terkait'),
        ('gangguan', '0008_gangguan_komponen_rusak_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='gangguan',
            name='layanan_icon',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='gangguan_terkait',
                to='devices.icon',
                verbose_name='Layanan ICON+',
                help_text='Opsional — pilih layanan ICON+ yang terdampak gangguan ini',
            ),
        ),
    ]
