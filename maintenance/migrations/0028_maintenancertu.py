from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('maintenance', '0027_alter_maintenanceradio_swr'),
    ]

    operations = [
        migrations.CreateModel(
            name='MaintenanceRTU',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('cp2016_jumlah', models.PositiveSmallIntegerField(blank=True, null=True, verbose_name='Jumlah CP-2016')),
                ('cp2016_data',   models.JSONField(blank=True, default=dict, verbose_name='Indikasi CP-2016')),
                ('cp2019_jumlah', models.PositiveSmallIntegerField(blank=True, null=True, verbose_name='Jumlah CP-2019')),
                ('cp2019_data',   models.JSONField(blank=True, default=dict, verbose_name='Indikasi CP-2019')),
                ('di2112_jumlah', models.PositiveSmallIntegerField(blank=True, null=True, verbose_name='Jumlah DI-2112/2113')),
                ('di2112_data',   models.JSONField(blank=True, default=dict, verbose_name='Indikasi DI-2112/2113')),
                ('do2210_jumlah', models.PositiveSmallIntegerField(blank=True, null=True, verbose_name='Jumlah DO-2210/2211')),
                ('do2210_data',   models.JSONField(blank=True, default=dict, verbose_name='Indikasi DO-2210/2211')),
                ('ai2300_data',   models.JSONField(blank=True, default=dict, verbose_name='Indikasi AI-2300')),
                ('ied_data',      models.JSONField(blank=True, default=dict, verbose_name='Indikasi IED')),
                ('ps48_teg_beban',   models.FloatField(blank=True, null=True, verbose_name='48V Tegangan Beban (V)')),
                ('ps48_arus_beban',  models.FloatField(blank=True, null=True, verbose_name='48V Arus Beban (A)')),
                ('ps48_teg_supply',  models.FloatField(blank=True, null=True, verbose_name='48V Tegangan Supply (V)')),
                ('ps110_teg_beban',  models.FloatField(blank=True, null=True, verbose_name='110V Tegangan Beban (V)')),
                ('ps110_arus_beban', models.FloatField(blank=True, null=True, verbose_name='110V Arus Beban (A)')),
                ('ps110_teg_supply', models.FloatField(blank=True, null=True, verbose_name='110V Tegangan Supply (V)')),
                ('ps110_arus_supply',models.FloatField(blank=True, null=True, verbose_name='110V Arus Supply (A)')),
                ('maintenance', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='maintenancertu',
                    to='maintenance.maintenance',
                )),
            ],
            options={'verbose_name': 'Maintenance RTU'},
        ),
    ]
