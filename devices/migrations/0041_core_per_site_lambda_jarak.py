from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('devices', '0040_fiberopticcore_lambda_fields'),
    ]

    operations = [
        # Core numbers per site
        migrations.AddField(
            model_name='fiberopticcore',
            name='nomor_core_a',
            field=models.PositiveIntegerField(
                blank=True, null=True, verbose_name='Nomor Core Site A',
                help_text='Nomor core sebagaimana tertera di ODF/panel Site A',
            ),
        ),
        migrations.AddField(
            model_name='fiberopticcore',
            name='nomor_core_b',
            field=models.PositiveIntegerField(
                blank=True, null=True, verbose_name='Nomor Core Site B',
                help_text='Nomor core sebagaimana tertera di ODF/panel Site B',
            ),
        ),
        # Jarak per wavelength — Site A
        migrations.AddField(
            model_name='fiberopticcore',
            name='otdr_jarak_km_1310',
            field=models.DecimalField(blank=True, decimal_places=4, max_digits=9, null=True, verbose_name='OTDR A Jarak λ1310 (km)'),
        ),
        migrations.AddField(
            model_name='fiberopticcore',
            name='otdr_jarak_km_1550',
            field=models.DecimalField(blank=True, decimal_places=4, max_digits=9, null=True, verbose_name='OTDR A Jarak λ1550 (km)'),
        ),
        # Jarak per wavelength — Site B
        migrations.AddField(
            model_name='fiberopticcore',
            name='otdr_b_jarak_km_1310',
            field=models.DecimalField(blank=True, decimal_places=4, max_digits=9, null=True, verbose_name='OTDR B Jarak λ1310 (km)'),
        ),
        migrations.AddField(
            model_name='fiberopticcore',
            name='otdr_b_jarak_km_1550',
            field=models.DecimalField(blank=True, decimal_places=4, max_digits=9, null=True, verbose_name='OTDR B Jarak λ1550 (km)'),
        ),
        # Remove old generic single-jarak fields (now replaced per-λ)
        migrations.RemoveField(model_name='fiberopticcore', name='otdr_jarak_km'),
        migrations.RemoveField(model_name='fiberopticcore', name='otdr_b_jarak_km'),
        # Remove old generic redaman/per_km (now replaced per-λ)
        migrations.RemoveField(model_name='fiberopticcore', name='otdr_redaman_db'),
        migrations.RemoveField(model_name='fiberopticcore', name='otdr_redaman_per_km'),
        migrations.RemoveField(model_name='fiberopticcore', name='otdr_b_redaman_db'),
        migrations.RemoveField(model_name='fiberopticcore', name='otdr_b_redaman_per_km'),
    ]
