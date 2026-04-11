from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('maintenance', '0035_maintenanceplc_modul_terpasang'),
    ]

    operations = [
        migrations.CreateModel(
            name='MaintenanceUPS',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('ups_merk',        models.CharField(blank=True, max_length=100, verbose_name='Merk UPS')),
                ('ups_model',       models.CharField(blank=True, max_length=100, verbose_name='Model UPS')),
                ('ups_kapasitas',   models.CharField(blank=True, max_length=50,  verbose_name='Kapasitas (VA/kVA)')),
                ('ups_kondisi',     models.CharField(blank=True, max_length=3,   verbose_name='Kondisi UPS')),
                ('v_input_r',       models.FloatField(blank=True, null=True, verbose_name='V Input R-N (V)')),
                ('v_input_s',       models.FloatField(blank=True, null=True, verbose_name='V Input S-N (V)')),
                ('v_input_t',       models.FloatField(blank=True, null=True, verbose_name='V Input T-N (V)')),
                ('f_input',         models.FloatField(blank=True, null=True, verbose_name='Frekuensi Input (Hz)')),
                ('v_output_r',      models.FloatField(blank=True, null=True, verbose_name='V Output R-N (V)')),
                ('v_output_s',      models.FloatField(blank=True, null=True, verbose_name='V Output S-N (V)')),
                ('v_output_t',      models.FloatField(blank=True, null=True, verbose_name='V Output T-N (V)')),
                ('f_output',        models.FloatField(blank=True, null=True, verbose_name='Frekuensi Output (Hz)')),
                ('a_load',          models.FloatField(blank=True, null=True, verbose_name='Arus Beban (A)')),
                ('percent_load',    models.FloatField(blank=True, null=True, verbose_name='Beban (%)')),
                ('bat_merk',        models.CharField(blank=True, max_length=100, verbose_name='Merk Battery')),
                ('bat_tipe',        models.CharField(blank=True, max_length=100, verbose_name='Tipe Battery')),
                ('bat_kapasitas',   models.CharField(blank=True, max_length=50,  verbose_name='Kapasitas Battery')),
                ('bat_jumlah_cell', models.IntegerField(blank=True, null=True, verbose_name='Jumlah Cell')),
                ('bat_kondisi',     models.CharField(blank=True, max_length=3, verbose_name='Kondisi Battery')),
                ('bat_kondisi_kabel', models.CharField(blank=True, max_length=3, verbose_name='Kondisi Kabel Battery')),
                ('bat_v_total',     models.FloatField(blank=True, null=True, verbose_name='V Total Battery (V)')),
                ('bat_cells',       models.JSONField(blank=True, default=list, verbose_name='Data Cell Battery')),
                ('catatan',         models.TextField(blank=True, default='')),
                ('maintenance', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    to='maintenance.maintenance',
                )),
            ],
            options={
                'verbose_name': 'Maintenance UPS',
            },
        ),
    ]
