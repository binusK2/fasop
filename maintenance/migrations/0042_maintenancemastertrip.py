from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('maintenance', '0041_maintenancefrequencyrelay'),
    ]

    operations = [
        migrations.CreateModel(
            name='MaintenanceMasterTrip',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                # Visual Inspection
                ('healthy',  models.CharField(blank=True, default='normal', max_length=20)),
                ('trip_led', models.CharField(blank=True, default='normal', max_length=20, verbose_name='Trip LED')),
                ('alarm',    models.CharField(blank=True, default='normal', max_length=20)),
                # Info
                ('merek',    models.CharField(blank=True, max_length=100)),
                ('no_seri',  models.CharField(blank=True, max_length=100, verbose_name='No. Seri')),
                ('target',   models.CharField(blank=True, max_length=150, verbose_name='Target (Trafo/Penyulang)')),
                ('fungsi',   models.CharField(blank=True, max_length=100, verbose_name='Fungsi')),
                ('rasio_ct', models.CharField(blank=True, max_length=50,  verbose_name='Rasio CT')),
                # Measurement
                ('i_a', models.CharField(blank=True, max_length=20)),
                ('i_b', models.CharField(blank=True, max_length=20)),
                ('i_c', models.CharField(blank=True, max_length=20)),
                ('v_a', models.CharField(blank=True, max_length=20)),
                ('v_b', models.CharField(blank=True, max_length=20)),
                ('v_c', models.CharField(blank=True, max_length=20)),
                ('frekuensi', models.CharField(blank=True, max_length=20)),
                # Setting Relay
                ('setting_i',   models.CharField(blank=True, max_length=20)),
                ('waktu_i',     models.CharField(blank=True, max_length=20)),
                ('setting_ii',  models.CharField(blank=True, max_length=20)),
                ('waktu_ii',    models.CharField(blank=True, max_length=20)),
                ('under_power', models.CharField(blank=True, max_length=20)),
                ('waktu_under', models.CharField(blank=True, max_length=20)),
                ('over_power',  models.CharField(blank=True, max_length=20)),
                ('waktu_over',  models.CharField(blank=True, max_length=20)),
                # Common Positif RL
                ('p1_rl', models.CharField(blank=True, max_length=20)), ('p1_vdc', models.CharField(blank=True, max_length=20)), ('p1_pin', models.CharField(blank=True, max_length=20)), ('p1_tahap_vdc', models.CharField(blank=True, max_length=20)), ('p1_tahap_pin', models.CharField(blank=True, max_length=20)),
                ('p2_rl', models.CharField(blank=True, max_length=20)), ('p2_vdc', models.CharField(blank=True, max_length=20)), ('p2_pin', models.CharField(blank=True, max_length=20)), ('p2_tahap_vdc', models.CharField(blank=True, max_length=20)), ('p2_tahap_pin', models.CharField(blank=True, max_length=20)),
                ('p3_rl', models.CharField(blank=True, max_length=20)), ('p3_vdc', models.CharField(blank=True, max_length=20)), ('p3_pin', models.CharField(blank=True, max_length=20)), ('p3_tahap_vdc', models.CharField(blank=True, max_length=20)), ('p3_tahap_pin', models.CharField(blank=True, max_length=20)),
                ('p4_rl', models.CharField(blank=True, max_length=20)), ('p4_vdc', models.CharField(blank=True, max_length=20)), ('p4_pin', models.CharField(blank=True, max_length=20)), ('p4_tahap_vdc', models.CharField(blank=True, max_length=20)), ('p4_tahap_pin', models.CharField(blank=True, max_length=20)),
                ('p5_rl', models.CharField(blank=True, max_length=20)), ('p5_vdc', models.CharField(blank=True, max_length=20)), ('p5_pin', models.CharField(blank=True, max_length=20)), ('p5_tahap_vdc', models.CharField(blank=True, max_length=20)), ('p5_tahap_pin', models.CharField(blank=True, max_length=20)),
                ('p6_rl', models.CharField(blank=True, max_length=20)), ('p6_vdc', models.CharField(blank=True, max_length=20)), ('p6_pin', models.CharField(blank=True, max_length=20)), ('p6_tahap_vdc', models.CharField(blank=True, max_length=20)), ('p6_tahap_pin', models.CharField(blank=True, max_length=20)),
                # Common Negatif RL
                ('n1_rl', models.CharField(blank=True, max_length=20)), ('n1_vdc', models.CharField(blank=True, max_length=20)), ('n1_pin', models.CharField(blank=True, max_length=20)), ('n1_tahap_vdc', models.CharField(blank=True, max_length=20)), ('n1_tahap_pin', models.CharField(blank=True, max_length=20)),
                ('n2_rl', models.CharField(blank=True, max_length=20)), ('n2_vdc', models.CharField(blank=True, max_length=20)), ('n2_pin', models.CharField(blank=True, max_length=20)), ('n2_tahap_vdc', models.CharField(blank=True, max_length=20)), ('n2_tahap_pin', models.CharField(blank=True, max_length=20)),
                ('n3_rl', models.CharField(blank=True, max_length=20)), ('n3_vdc', models.CharField(blank=True, max_length=20)), ('n3_pin', models.CharField(blank=True, max_length=20)), ('n3_tahap_vdc', models.CharField(blank=True, max_length=20)), ('n3_tahap_pin', models.CharField(blank=True, max_length=20)),
                ('n4_rl', models.CharField(blank=True, max_length=20)), ('n4_vdc', models.CharField(blank=True, max_length=20)), ('n4_pin', models.CharField(blank=True, max_length=20)), ('n4_tahap_vdc', models.CharField(blank=True, max_length=20)), ('n4_tahap_pin', models.CharField(blank=True, max_length=20)),
                ('n5_rl', models.CharField(blank=True, max_length=20)), ('n5_vdc', models.CharField(blank=True, max_length=20)), ('n5_pin', models.CharField(blank=True, max_length=20)), ('n5_tahap_vdc', models.CharField(blank=True, max_length=20)), ('n5_tahap_pin', models.CharField(blank=True, max_length=20)),
                ('n6_rl', models.CharField(blank=True, max_length=20)), ('n6_vdc', models.CharField(blank=True, max_length=20)), ('n6_pin', models.CharField(blank=True, max_length=20)), ('n6_tahap_vdc', models.CharField(blank=True, max_length=20)), ('n6_tahap_pin', models.CharField(blank=True, max_length=20)),
                # AUX RL/BO
                ('aux1_rl', models.CharField(blank=True, max_length=30)), ('aux1_tf', models.CharField(blank=True, max_length=30)), ('aux1_led', models.CharField(blank=True, max_length=30)),
                ('aux2_rl', models.CharField(blank=True, max_length=30)), ('aux2_tf', models.CharField(blank=True, max_length=30)), ('aux2_led', models.CharField(blank=True, max_length=30)),
                ('aux3_rl', models.CharField(blank=True, max_length=30)), ('aux3_tf', models.CharField(blank=True, max_length=30)), ('aux3_led', models.CharField(blank=True, max_length=30)),
                ('aux4_rl', models.CharField(blank=True, max_length=30)), ('aux4_tf', models.CharField(blank=True, max_length=30)), ('aux4_led', models.CharField(blank=True, max_length=30)),
                ('aux5_rl', models.CharField(blank=True, max_length=30)), ('aux5_tf', models.CharField(blank=True, max_length=30)), ('aux5_led', models.CharField(blank=True, max_length=30)),
                ('aux6_rl', models.CharField(blank=True, max_length=30)), ('aux6_tf', models.CharField(blank=True, max_length=30)), ('aux6_led', models.CharField(blank=True, max_length=30)),
                # Status Kesiapan + Test COMM
                ('dev1_nama', models.CharField(blank=True, max_length=100)), ('dev1_gi', models.CharField(blank=True, max_length=100)), ('dev1_ready', models.CharField(blank=True, default='READY', max_length=5)), ('dev1_comm', models.CharField(blank=True, default='OK', max_length=3)),
                ('dev2_nama', models.CharField(blank=True, max_length=100)), ('dev2_gi', models.CharField(blank=True, max_length=100)), ('dev2_ready', models.CharField(blank=True, default='READY', max_length=5)), ('dev2_comm', models.CharField(blank=True, default='OK', max_length=3)),
                ('dev3_nama', models.CharField(blank=True, max_length=100)), ('dev3_gi', models.CharField(blank=True, max_length=100)), ('dev3_ready', models.CharField(blank=True, default='READY', max_length=5)), ('dev3_comm', models.CharField(blank=True, default='OK', max_length=3)),
                ('dev4_nama', models.CharField(blank=True, max_length=100)), ('dev4_gi', models.CharField(blank=True, max_length=100)), ('dev4_ready', models.CharField(blank=True, default='READY', max_length=5)), ('dev4_comm', models.CharField(blank=True, default='OK', max_length=3)),
                ('dev5_nama', models.CharField(blank=True, max_length=100)), ('dev5_gi', models.CharField(blank=True, max_length=100)), ('dev5_ready', models.CharField(blank=True, default='READY', max_length=5)), ('dev5_comm', models.CharField(blank=True, default='OK', max_length=3)),
                ('dev6_nama', models.CharField(blank=True, max_length=100)), ('dev6_gi', models.CharField(blank=True, max_length=100)), ('dev6_ready', models.CharField(blank=True, default='READY', max_length=5)), ('dev6_comm', models.CharField(blank=True, default='OK', max_length=3)),
                # Catatan
                ('supply_dc', models.CharField(blank=True, max_length=50)),
                ('selektor',  models.CharField(blank=True, max_length=50)),
                ('catatan',   models.TextField(blank=True)),
                # FK
                ('maintenance', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='maintenancemastertrip',
                    to='maintenance.maintenance',
                )),
            ],
            options={
                'verbose_name': 'Maintenance Master Trip',
            },
        ),
    ]
