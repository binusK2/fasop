from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('devices', '0034_fiberoptic_konfigurasi_fiberopticcore_koneksi'),
    ]

    operations = [
        migrations.AddField(
            model_name='fiberopticcore',
            name='otdr_b_jarak_km',
            field=models.DecimalField(
                blank=True, null=True, max_digits=8, decimal_places=3,
                verbose_name='OTDR B Jarak (km)',
                help_text='Jarak total atau jarak ke titik gangguan dari Site B',
            ),
        ),
        migrations.AddField(
            model_name='fiberopticcore',
            name='otdr_b_redaman_db',
            field=models.DecimalField(
                blank=True, null=True, max_digits=6, decimal_places=3,
                verbose_name='OTDR B Redaman (dB)',
                help_text='Total redaman kabel diukur dari Site B',
            ),
        ),
        migrations.AddField(
            model_name='fiberopticcore',
            name='otdr_b_redaman_per_km',
            field=models.DecimalField(
                blank=True, null=True, max_digits=5, decimal_places=3,
                verbose_name='OTDR B Redaman per km (dB/km)',
            ),
        ),
        migrations.AddField(
            model_name='fiberopticcore',
            name='otdr_b_tanggal',
            field=models.DateField(
                blank=True, null=True,
                verbose_name='OTDR B Tanggal Pengukuran',
            ),
        ),
        migrations.AddField(
            model_name='fiberopticcore',
            name='otdr_b_catatan',
            field=models.TextField(
                blank=True, null=True,
                verbose_name='OTDR B Catatan',
                help_text='Temuan, anomali, atau catatan hasil pengukuran dari Site B',
            ),
        ),
    ]
