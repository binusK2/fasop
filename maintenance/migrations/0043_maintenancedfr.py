from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('maintenance', '0042_maintenancemastertrip'),
    ]

    operations = [
        migrations.CreateModel(
            name='MaintenanceDFR',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                # Header
                ('bay_feeder_1', models.CharField(blank=True, max_length=100, verbose_name='BAY/FEEDER 1')),
                ('bay_feeder_2', models.CharField(blank=True, max_length=100, verbose_name='BAY/FEEDER 2')),
                ('rasio_ct_1',   models.CharField(blank=True, max_length=50,  verbose_name='Rasio CT 1')),
                ('rasio_ct_2',   models.CharField(blank=True, max_length=50,  verbose_name='Rasio CT 2')),
                ('rasio_pt_1',   models.CharField(blank=True, max_length=50,  verbose_name='Rasio PT 1')),
                ('rasio_pt_2',   models.CharField(blank=True, max_length=50,  verbose_name='Rasio PT 2')),
                ('suhu_ruangan', models.CharField(blank=True, max_length=20,  verbose_name='Suhu Ruangan (°C)')),
                ('kelembaban',   models.CharField(blank=True, max_length=20,  verbose_name='Kelembaban (%)')),
                # Section I
                ('kartu_kontrol', models.CharField(blank=True, default='Terisi', max_length=30)),
                ('outdoor_panel', models.CharField(blank=True, default='Bersih', max_length=30)),
                ('indoor_panel',  models.CharField(blank=True, default='Bersih', max_length=30)),
                ('type_dfr',      models.CharField(blank=True, max_length=50,  verbose_name='Type DFR')),
                ('sn_dfr',        models.CharField(blank=True, max_length=100, verbose_name='SN DFR')),
                ('merk_dfr',      models.CharField(blank=True, max_length=100, verbose_name='Merk DFR')),
                ('tergrounding',  models.CharField(blank=True, default='Ya', max_length=5, verbose_name='Tergrounding')),
                # Section II
                ('kondisi_gps', models.CharField(blank=True, default='Terhubung', max_length=15)),
                ('kondisi_lcd', models.CharField(blank=True, default='Normal',    max_length=10)),
                ('waktu_dfr',   models.CharField(blank=True, default='Sesuai',    max_length=30)),
                # Section III
                ('dfr_aktif',      models.CharField(blank=True, default='Ya',     max_length=5)),
                ('fisik_alarm',    models.CharField(blank=True, default='Baik',   max_length=15)),
                ('fungsi_rekaman', models.CharField(blank=True, default='Normal', max_length=10)),
                # Section IV
                ('visual_5r',          models.CharField(blank=True, default='Baik',        max_length=15)),
                ('front_port_ip',      models.CharField(blank=True, max_length=50)),
                ('rear_port_ip',       models.CharField(blank=True, max_length=50)),
                ('fo_tx',              models.CharField(blank=True, default='Normal', max_length=10)),
                ('fo_rx',              models.CharField(blank=True, default='Normal', max_length=10)),
                ('conv_tx',            models.CharField(blank=True, default='Normal', max_length=10)),
                ('conv_rx',            models.CharField(blank=True, default='Normal', max_length=10)),
                ('lan_tx',             models.CharField(blank=True, default='Normal', max_length=10)),
                ('lan_rx',             models.CharField(blank=True, default='Normal', max_length=10)),
                ('ping_server_1',      models.CharField(blank=True, max_length=10)),
                ('ping_server_2',      models.CharField(blank=True, max_length=10)),
                ('ping_server_status', models.CharField(blank=True, default='Normal', max_length=10)),
                ('ping_dfr_1',         models.CharField(blank=True, max_length=10)),
                ('ping_dfr_2',         models.CharField(blank=True, max_length=10)),
                ('ping_dfr_status',    models.CharField(blank=True, default='Normal', max_length=10)),
                # Section V
                ('software_config',  models.CharField(blank=True, default='Terdownload', max_length=15)),
                ('rekaman_gangguan', models.CharField(blank=True, default='Terdownload', max_length=15)),
                ('v_input_power',    models.CharField(blank=True, max_length=20)),
                ('v_backup',         models.CharField(blank=True, max_length=20)),
                ('kapasitas_memory', models.CharField(blank=True, max_length=30)),
                ('catatan_khusus',   models.TextField(blank=True)),
                ('pmu_id',           models.CharField(blank=True, max_length=100)),
                # Bay 1 DFR
                ('bay1_dfr_v_r', models.CharField(blank=True, max_length=20)), ('bay1_dfr_v_s', models.CharField(blank=True, max_length=20)), ('bay1_dfr_v_t', models.CharField(blank=True, max_length=20)), ('bay1_dfr_v_n', models.CharField(blank=True, max_length=20)),
                ('bay1_dfr_i_r', models.CharField(blank=True, max_length=20)), ('bay1_dfr_i_s', models.CharField(blank=True, max_length=20)), ('bay1_dfr_i_t', models.CharField(blank=True, max_length=20)), ('bay1_dfr_i_n', models.CharField(blank=True, max_length=20)),
                ('bay1_dfr_hz',  models.CharField(blank=True, max_length=20)),
                # Bay 1 IED
                ('bay1_ied_v_r', models.CharField(blank=True, max_length=20)), ('bay1_ied_v_s', models.CharField(blank=True, max_length=20)), ('bay1_ied_v_t', models.CharField(blank=True, max_length=20)), ('bay1_ied_v_n', models.CharField(blank=True, max_length=20)),
                ('bay1_ied_i_r', models.CharField(blank=True, max_length=20)), ('bay1_ied_i_s', models.CharField(blank=True, max_length=20)), ('bay1_ied_i_t', models.CharField(blank=True, max_length=20)), ('bay1_ied_i_n', models.CharField(blank=True, max_length=20)),
                ('bay1_ied_hz',  models.CharField(blank=True, max_length=20)),
                # Bay 2 DFR
                ('bay2_dfr_v_r', models.CharField(blank=True, max_length=20)), ('bay2_dfr_v_s', models.CharField(blank=True, max_length=20)), ('bay2_dfr_v_t', models.CharField(blank=True, max_length=20)), ('bay2_dfr_v_n', models.CharField(blank=True, max_length=20)),
                ('bay2_dfr_i_r', models.CharField(blank=True, max_length=20)), ('bay2_dfr_i_s', models.CharField(blank=True, max_length=20)), ('bay2_dfr_i_t', models.CharField(blank=True, max_length=20)), ('bay2_dfr_i_n', models.CharField(blank=True, max_length=20)),
                ('bay2_dfr_hz',  models.CharField(blank=True, max_length=20)),
                # Bay 2 IED
                ('bay2_ied_v_r', models.CharField(blank=True, max_length=20)), ('bay2_ied_v_s', models.CharField(blank=True, max_length=20)), ('bay2_ied_v_t', models.CharField(blank=True, max_length=20)), ('bay2_ied_v_n', models.CharField(blank=True, max_length=20)),
                ('bay2_ied_i_r', models.CharField(blank=True, max_length=20)), ('bay2_ied_i_s', models.CharField(blank=True, max_length=20)), ('bay2_ied_i_t', models.CharField(blank=True, max_length=20)), ('bay2_ied_i_n', models.CharField(blank=True, max_length=20)),
                ('bay2_ied_hz',  models.CharField(blank=True, max_length=20)),
                # FK
                ('maintenance', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='maintenancedfr',
                    to='maintenance.maintenance',
                )),
            ],
            options={'verbose_name': 'Maintenance DFR'},
        ),
    ]
