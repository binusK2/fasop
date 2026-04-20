from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('devices', '0039_fiberopticcore_jarak_4dp'),
    ]

    operations = [
        # λ1310 Site A
        migrations.AddField(
            model_name='fiberopticcore',
            name='otdr_redaman_db_1310',
            field=models.DecimalField(blank=True, decimal_places=3, max_digits=6, null=True, verbose_name='OTDR A Redaman λ1310 (dB)'),
        ),
        migrations.AddField(
            model_name='fiberopticcore',
            name='otdr_redaman_per_km_1310',
            field=models.DecimalField(blank=True, decimal_places=3, max_digits=5, null=True, verbose_name='OTDR A Avg Loss λ1310 (dB/km)'),
        ),
        # λ1550 Site A
        migrations.AddField(
            model_name='fiberopticcore',
            name='otdr_redaman_db_1550',
            field=models.DecimalField(blank=True, decimal_places=3, max_digits=6, null=True, verbose_name='OTDR A Redaman λ1550 (dB)'),
        ),
        migrations.AddField(
            model_name='fiberopticcore',
            name='otdr_redaman_per_km_1550',
            field=models.DecimalField(blank=True, decimal_places=3, max_digits=5, null=True, verbose_name='OTDR A Avg Loss λ1550 (dB/km)'),
        ),
        # λ1310 Site B
        migrations.AddField(
            model_name='fiberopticcore',
            name='otdr_b_redaman_db_1310',
            field=models.DecimalField(blank=True, decimal_places=3, max_digits=6, null=True, verbose_name='OTDR B Redaman λ1310 (dB)'),
        ),
        migrations.AddField(
            model_name='fiberopticcore',
            name='otdr_b_redaman_per_km_1310',
            field=models.DecimalField(blank=True, decimal_places=3, max_digits=5, null=True, verbose_name='OTDR B Avg Loss λ1310 (dB/km)'),
        ),
        # λ1550 Site B
        migrations.AddField(
            model_name='fiberopticcore',
            name='otdr_b_redaman_db_1550',
            field=models.DecimalField(blank=True, decimal_places=3, max_digits=6, null=True, verbose_name='OTDR B Redaman λ1550 (dB)'),
        ),
        migrations.AddField(
            model_name='fiberopticcore',
            name='otdr_b_redaman_per_km_1550',
            field=models.DecimalField(blank=True, decimal_places=3, max_digits=5, null=True, verbose_name='OTDR B Avg Loss λ1550 (dB/km)'),
        ),
    ]
