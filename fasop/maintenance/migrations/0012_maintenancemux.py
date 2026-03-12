from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('maintenance', '0011_maintenancevoip_sip_servers'),
    ]

    operations = [
        migrations.CreateModel(
            name='MaintenanceMux',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                # Kondisi Lingkungan
                ('suhu_ruangan',     models.FloatField(blank=True, null=True, verbose_name='Suhu Ruangan (°C)')),
                ('kebersihan',       models.CharField(blank=True, max_length=10, choices=[('Bersih','Bersih'),('Kotor','Kotor')])),
                ('lampu_penerangan', models.CharField(blank=True, max_length=15, choices=[('Menyala','Menyala'),('Tidak Menyala','Tidak Menyala'),('Redup','Redup')])),
                # Peralatan Terpasang
                ('brand',            models.CharField(blank=True, max_length=100, verbose_name='Brand')),
                ('firmware',         models.CharField(blank=True, max_length=100, verbose_name='Firmware')),
                ('sync_source_1',    models.CharField(blank=True, max_length=100, verbose_name='Sync Source 1')),
                ('sync_source_2',    models.CharField(blank=True, max_length=100, verbose_name='Sync Source 2')),
                # CPU
                ('cpu_1',            models.TextField(blank=True, verbose_name='CPU 1')),
                ('cpu_2',            models.TextField(blank=True, verbose_name='CPU 2')),
                # HS 1
                ('hs1_merk',         models.CharField(blank=True, max_length=100)),
                ('hs1_tx_bias',      models.FloatField(blank=True, null=True, verbose_name='HS1 TX Bias (mA)')),
                ('hs1_jarak',        models.FloatField(blank=True, null=True, verbose_name='HS1 Jarak (km)')),
                ('hs1_tx',           models.FloatField(blank=True, null=True, verbose_name='HS1 Nilai TX (dBm)')),
                ('hs1_lambda',       models.FloatField(blank=True, null=True, verbose_name='HS1 Lambda (nm)')),
                ('hs1_suhu',         models.FloatField(blank=True, null=True, verbose_name='HS1 Suhu (°C)')),
                ('hs1_rx',           models.FloatField(blank=True, null=True, verbose_name='HS1 Nilai RX (dBm)')),
                ('hs1_bandwidth',    models.CharField(blank=True, max_length=50, verbose_name='HS1 Bandwidth')),
                # HS 2
                ('hs2_merk',         models.CharField(blank=True, max_length=100)),
                ('hs2_tx_bias',      models.FloatField(blank=True, null=True, verbose_name='HS2 TX Bias (mA)')),
                ('hs2_jarak',        models.FloatField(blank=True, null=True, verbose_name='HS2 Jarak (km)')),
                ('hs2_tx',           models.FloatField(blank=True, null=True, verbose_name='HS2 Nilai TX (dBm)')),
                ('hs2_lambda',       models.FloatField(blank=True, null=True, verbose_name='HS2 Lambda (nm)')),
                ('hs2_suhu',         models.FloatField(blank=True, null=True, verbose_name='HS2 Suhu (°C)')),
                ('hs2_rx',           models.FloatField(blank=True, null=True, verbose_name='HS2 Nilai RX (dBm)')),
                ('hs2_bandwidth',    models.CharField(blank=True, max_length=50, verbose_name='HS2 Bandwidth')),
                # Slot A–H
                ('slot_a_modul', models.CharField(blank=True, max_length=100)), ('slot_a_isian', models.TextField(blank=True)),
                ('slot_b_modul', models.CharField(blank=True, max_length=100)), ('slot_b_isian', models.TextField(blank=True)),
                ('slot_c_modul', models.CharField(blank=True, max_length=100)), ('slot_c_isian', models.TextField(blank=True)),
                ('slot_d_modul', models.CharField(blank=True, max_length=100)), ('slot_d_isian', models.TextField(blank=True)),
                ('slot_e_modul', models.CharField(blank=True, max_length=100)), ('slot_e_isian', models.TextField(blank=True)),
                ('slot_f_modul', models.CharField(blank=True, max_length=100)), ('slot_f_isian', models.TextField(blank=True)),
                ('slot_g_modul', models.CharField(blank=True, max_length=100)), ('slot_g_isian', models.TextField(blank=True)),
                ('slot_h_modul', models.CharField(blank=True, max_length=100)), ('slot_h_isian', models.TextField(blank=True)),
                # PSU 1
                ('psu1_status', models.CharField(blank=True, max_length=3, choices=[('OK','OK'),('NOK','NOK')])),
                ('psu1_temp1',  models.FloatField(blank=True, null=True)),
                ('psu1_temp2',  models.FloatField(blank=True, null=True)),
                ('psu1_temp3',  models.FloatField(blank=True, null=True)),
                # PSU 2
                ('psu2_status', models.CharField(blank=True, max_length=3, choices=[('OK','OK'),('NOK','NOK')])),
                ('psu2_temp1',  models.FloatField(blank=True, null=True)),
                ('psu2_temp2',  models.FloatField(blank=True, null=True)),
                ('psu2_temp3',  models.FloatField(blank=True, null=True)),
                # FAN + Catatan
                ('fan_status',  models.CharField(blank=True, max_length=3, choices=[('OK','OK'),('NOK','NOK')])),
                ('catatan',     models.TextField(blank=True, verbose_name='Catatan')),
                ('maintenance', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, to='maintenance.maintenance')),
            ],
            options={'verbose_name': 'Maintenance Multiplexer'},
        ),
    ]
