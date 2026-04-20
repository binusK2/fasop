from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('devices', '0038_device_wiring'),
    ]

    operations = [
        migrations.AlterField(
            model_name='fiberopticcore',
            name='otdr_jarak_km',
            field=models.DecimalField(
                blank=True, decimal_places=4, max_digits=9, null=True,
                verbose_name='OTDR A Jarak (km)',
                help_text='Jarak total atau jarak ke titik gangguan dari Site A',
            ),
        ),
        migrations.AlterField(
            model_name='fiberopticcore',
            name='otdr_b_jarak_km',
            field=models.DecimalField(
                blank=True, decimal_places=4, max_digits=9, null=True,
                verbose_name='OTDR B Jarak (km)',
                help_text='Jarak total atau jarak ke titik gangguan dari Site B',
            ),
        ),
    ]
