from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('maintenance', '0024_maintenanceteleproteksi'),
    ]

    operations = [
        migrations.CreateModel(
            name='MaintenanceGenset',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                # Batere
                ('air_accu',            models.FloatField(blank=True, null=True, verbose_name='Air Accu (mm)')),
                ('tegangan_batere',     models.FloatField(blank=True, null=True, verbose_name='Tegangan Batere (VDC)')),
                ('arus_pengisian',      models.FloatField(blank=True, null=True, verbose_name='Arus Pengisian (A)')),
                # Charger
                ('tegangan_charger',    models.FloatField(blank=True, null=True, verbose_name='Tegangan Charger (VDC)')),
                ('arus_beban_charger',  models.FloatField(blank=True, null=True, verbose_name='Arus Beban Charger (A)')),
                # Genset utama
                ('radiator',            models.FloatField(blank=True, null=True, verbose_name='Radiator (°C)')),
                ('kapasitas_tangki',    models.FloatField(blank=True, null=True, verbose_name='Kapasitas Tangki (liter)')),
                ('tangki_bbm_sebelum',  models.FloatField(blank=True, null=True, verbose_name='Tangki BBM Sebelum (liter)')),
                ('tangki_bbm_sesudah',  models.FloatField(blank=True, null=True, verbose_name='Tangki BBM Sesudah (liter)')),
                ('mcb',                 models.CharField(blank=True, max_length=3, verbose_name='MCB', choices=[('ON','ON'),('OFF','OFF')])),
                ('pelumas',             models.CharField(blank=True, max_length=100, verbose_name='Pelumas')),
                # Waktu transisi
                ('waktu_transisi',      models.FloatField(blank=True, null=True, verbose_name='Waktu Transisi (detik)')),
                # PLN R/S/T
                ('pln_f_r',  models.FloatField(blank=True, null=True, verbose_name='PLN Frekuensi R-N (Hz)')),
                ('pln_f_s',  models.FloatField(blank=True, null=True, verbose_name='PLN Frekuensi S-N (Hz)')),
                ('pln_f_t',  models.FloatField(blank=True, null=True, verbose_name='PLN Frekuensi T-N (Hz)')),
                ('pln_v_rn', models.FloatField(blank=True, null=True, verbose_name='PLN Teg 1Ph R-N (V)')),
                ('pln_v_sn', models.FloatField(blank=True, null=True, verbose_name='PLN Teg 1Ph S-N (V)')),
                ('pln_v_tn', models.FloatField(blank=True, null=True, verbose_name='PLN Teg 1Ph T-N (V)')),
                ('pln_v_rs', models.FloatField(blank=True, null=True, verbose_name='PLN Teg 3Ph R-S (V)')),
                ('pln_v_st', models.FloatField(blank=True, null=True, verbose_name='PLN Teg 3Ph S-T (V)')),
                ('pln_v_tr', models.FloatField(blank=True, null=True, verbose_name='PLN Teg 3Ph T-R (V)')),
                ('pln_i_r',  models.FloatField(blank=True, null=True, verbose_name='PLN Arus R (A)')),
                ('pln_i_s',  models.FloatField(blank=True, null=True, verbose_name='PLN Arus S (A)')),
                ('pln_i_t',  models.FloatField(blank=True, null=True, verbose_name='PLN Arus T (A)')),
                # Genset R/S/T
                ('gen_f_r',  models.FloatField(blank=True, null=True, verbose_name='Genset Frekuensi R-N (Hz)')),
                ('gen_f_s',  models.FloatField(blank=True, null=True, verbose_name='Genset Frekuensi S-N (Hz)')),
                ('gen_f_t',  models.FloatField(blank=True, null=True, verbose_name='Genset Frekuensi T-N (Hz)')),
                ('gen_v_rn', models.FloatField(blank=True, null=True, verbose_name='Genset Teg 1Ph R-N (V)')),
                ('gen_v_sn', models.FloatField(blank=True, null=True, verbose_name='Genset Teg 1Ph S-N (V)')),
                ('gen_v_tn', models.FloatField(blank=True, null=True, verbose_name='Genset Teg 1Ph T-N (V)')),
                ('gen_v_rs', models.FloatField(blank=True, null=True, verbose_name='Genset Teg 3Ph R-S (V)')),
                ('gen_v_st', models.FloatField(blank=True, null=True, verbose_name='Genset Teg 3Ph S-T (V)')),
                ('gen_v_tr', models.FloatField(blank=True, null=True, verbose_name='Genset Teg 3Ph T-R (V)')),
                ('gen_i_r',  models.FloatField(blank=True, null=True, verbose_name='Genset Arus R (A)')),
                ('gen_i_s',  models.FloatField(blank=True, null=True, verbose_name='Genset Arus S (A)')),
                ('gen_i_t',  models.FloatField(blank=True, null=True, verbose_name='Genset Arus T (A)')),
                # MDF Cubicle
                ('oil_pressure',       models.FloatField(blank=True, null=True, verbose_name='Oil Pressure (Kpa)')),
                ('engine_temperature', models.FloatField(blank=True, null=True, verbose_name='Engine Temperature (°C)')),
                ('batere_condition',   models.FloatField(blank=True, null=True, verbose_name='Batere Condition (VDC)')),
                ('rpm',                models.FloatField(blank=True, null=True, verbose_name='RPM')),
                # Counter
                ('counter_sebelum', models.FloatField(blank=True, null=True, verbose_name='Counter Sebelum (jam)')),
                ('counter_sesudah', models.FloatField(blank=True, null=True, verbose_name='Counter Sesudah (jam)')),
                # Jam Operasi
                ('waktu_start', models.TimeField(blank=True, null=True, verbose_name='Waktu Start')),
                ('waktu_stop',  models.TimeField(blank=True, null=True, verbose_name='Waktu Stop')),
                # Catatan
                ('catatan', models.TextField(blank=True, verbose_name='Catatan')),
                ('maintenance', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    to='maintenance.maintenance'
                )),
            ],
            options={'verbose_name': 'Maintenance Genset'},
        ),
    ]
