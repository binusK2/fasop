# Generated for Early Warning WhatsApp (device_mon RTU)

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('device_mon', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='RTUAlertLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('jenis', models.CharField(choices=[('DOWN', 'RTU Down'), ('UP', 'RTU Pulih')], max_length=10)),
                ('pesan', models.TextField(verbose_name='Isi pesan')),
                ('terkirim', models.BooleanField(default=False, verbose_name='Terkirim')),
                ('keterangan', models.CharField(blank=True, max_length=255, verbose_name='Keterangan / error')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('rtu', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='alerts', to='device_mon.rtu')),
            ],
            options={
                'verbose_name': 'Log Early Warning WA',
                'verbose_name_plural': 'Log Early Warning WA',
                'ordering': ['-created_at'],
                'indexes': [models.Index(fields=['rtu', '-created_at'], name='devmon_alert_rtu_created_idx')],
            },
        ),
    ]
