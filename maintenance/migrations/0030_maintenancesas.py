from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('maintenance', '0029_maintenancertu_ps48_arus_supply'),
    ]

    operations = [
        migrations.CreateModel(
            name='MaintenanceSAS',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                # Spesifikasi
                ('spek_merk',       models.CharField(blank=True, default='', max_length=100, verbose_name='Merk')),
                ('spek_type',       models.CharField(blank=True, default='', max_length=100, verbose_name='Type')),
                ('spek_cpu',        models.CharField(blank=True, default='', max_length=100, verbose_name='CPU')),
                ('spek_ram',        models.CharField(blank=True, default='', max_length=100, verbose_name='RAM')),
                ('spek_gpu',        models.CharField(blank=True, default='', max_length=100, verbose_name='GPU')),
                ('spek_storage',    models.CharField(blank=True, default='', max_length=100, verbose_name='Storage Memory')),
                ('spek_firmware',   models.CharField(blank=True, default='', max_length=100, verbose_name='Firmware Version')),
                ('spek_config_ver', models.CharField(blank=True, default='', max_length=100, verbose_name='Configuration Version')),
                ('spek_ip',         models.CharField(blank=True, default='', max_length=50,  verbose_name='Maintenance IP')),
                ('modul_io',        models.TextField(blank=True, default='', verbose_name='Modul I/O / Card / Terminal Terpasang')),
                # Kondisi Peralatan
                ('kondisi_server',  models.CharField(blank=True, default='', max_length=20, verbose_name='Kondisi Server/Gateway', choices=[('BERSIH', 'Bersih'), ('TIDAK BERSIH', 'Tidak Bersih')])),
                ('kondisi_panel',   models.CharField(blank=True, default='', max_length=20, verbose_name='Kondisi Panel', choices=[('BERSIH', 'Bersih'), ('TIDAK BERSIH', 'Tidak Bersih')])),
                ('temp_ruangan',    models.FloatField(blank=True, null=True, verbose_name='Temperatur Ruangan (°C)')),
                ('temp_peralatan',  models.FloatField(blank=True, null=True, verbose_name='Temperatur Peralatan (°C)')),
                ('exhaust_fan',     models.CharField(blank=True, default='', max_length=30, verbose_name='Exhaust Fan', choices=[('ADA, BERFUNGSI', 'Ada, Berfungsi'), ('ADA, TIDAK BERFUNGSI', 'Ada, Tidak Berfungsi'), ('TIDAK ADA', 'Tidak Ada')])),
                # Peripheral
                ('peri_eth_switch', models.CharField(blank=True, default='', max_length=10, verbose_name='Ethernet Switch', choices=[('OK', 'OK'), ('ALARM', 'Alarm')])),
                ('peri_gps',        models.CharField(blank=True, default='', max_length=10, verbose_name='GPS', choices=[('OK', 'OK'), ('ALARM', 'Alarm')])),
                ('peri_eth_serial', models.CharField(blank=True, default='', max_length=10, verbose_name='Ethernet to Serial', choices=[('OK', 'OK'), ('ALARM', 'Alarm')])),
                ('peri_router',     models.CharField(blank=True, default='', max_length=10, verbose_name='Router', choices=[('OK', 'OK'), ('ALARM', 'Alarm')])),
                ('jumlah_bay',      models.PositiveSmallIntegerField(blank=True, null=True, verbose_name='Jumlah Bay')),
                ('peri_keterangan', models.TextField(blank=True, default='', verbose_name='Keterangan Peripheral')),
                # Performa
                ('perf_cpu',        models.CharField(blank=True, default='', max_length=20, verbose_name='CPU Terpakai')),
                ('perf_ram',        models.CharField(blank=True, default='', max_length=20, verbose_name='RAM Terpakai')),
                ('perf_storage',    models.CharField(blank=True, default='', max_length=20, verbose_name='Storage Terpakai')),
                ('indikasi_alarm',  models.CharField(blank=True, default='', max_length=15, verbose_name='Indikasi Alarm/Error', choices=[('ADA', 'Ada'), ('TIDAK ADA', 'Tidak Ada')])),
                ('komm_master',     models.CharField(blank=True, default='', max_length=10, verbose_name='Komunikasi ke Master Station', choices=[('OK', 'OK'), ('ALARM', 'Alarm')])),
                ('komm_ied',        models.CharField(blank=True, default='', max_length=10, verbose_name='Komunikasi ke IED', choices=[('OK', 'OK'), ('ALARM', 'Alarm')])),
                ('time_sync',       models.CharField(blank=True, default='', max_length=10, verbose_name='Time Synchronization', choices=[('OK', 'OK'), ('NOK', 'NOK')])),
                # Power Supply — Inverter
                ('inv_kondisi',     models.CharField(blank=True, default='', max_length=10, verbose_name='Inverter Kondisi', choices=[('OK', 'OK'), ('ALARM', 'Alarm')])),
                ('inv_teg_input',   models.FloatField(blank=True, null=True, verbose_name='Inverter Tegangan Input (V)')),
                ('inv_arus_input',  models.FloatField(blank=True, null=True, verbose_name='Inverter Arus Input (A)')),
                ('inv_teg_output',  models.FloatField(blank=True, null=True, verbose_name='Inverter Tegangan Output (V)')),
                ('inv_arus_output', models.FloatField(blank=True, null=True, verbose_name='Inverter Arus Output (A)')),
                # Power Supply — 110VDC/48VDC
                ('ps_teg_input',    models.FloatField(blank=True, null=True, verbose_name='PS Tegangan Input (V)')),
                ('ps_arus_input',   models.FloatField(blank=True, null=True, verbose_name='PS Arus Input (A)')),
                ('ps_teg_output',   models.FloatField(blank=True, null=True, verbose_name='PS Tegangan Output (V)')),
                ('ps_arus_output',  models.FloatField(blank=True, null=True, verbose_name='PS Arus Output (A)')),
                # FK
                ('maintenance', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='maintenancesas',
                    to='maintenance.maintenance',
                )),
            ],
            options={
                'verbose_name': 'Maintenance SAS',
            },
        ),
    ]
