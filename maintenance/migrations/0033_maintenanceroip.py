from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('maintenance', '0032_maintenancerectifier_rect1_v_load'),
    ]

    operations = [
        migrations.CreateModel(
            name='MaintenanceRoIP',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('kondisi_fisik',    models.CharField(blank=True, max_length=3, choices=[('OK','OK'),('NOK','NOK')], verbose_name='Kondisi Fisik Perangkat')),
                ('ntp_server',       models.CharField(blank=True, max_length=3, choices=[('OK','OK'),('NOK','NOK')], verbose_name='NTP Server')),
                ('power_supply',     models.CharField(blank=True, max_length=3, choices=[('OK','OK'),('NOK','NOK')], verbose_name='Power Supply')),
                ('memory_usage',     models.FloatField(blank=True, null=True, verbose_name='Memory Usage (%)')),
                ('tx_volume_offset', models.FloatField(blank=True, null=True, verbose_name='TX Volume Offset to Transceiver (dB)')),
                ('rx_volume_offset', models.FloatField(blank=True, null=True, verbose_name='RX Volume Offset from Transceiver (dB)')),
                ('ptt_attack_time',   models.FloatField(blank=True, null=True, verbose_name='PTT Attack Time (ms)')),
                ('ptt_release_time',  models.FloatField(blank=True, null=True, verbose_name='PTT Release Time (ms)')),
                ('ptt_voice_delay',   models.FloatField(blank=True, null=True, verbose_name='PTT Voice Delay (ms)')),
                ('ptt_vox_threshold', models.FloatField(blank=True, null=True, verbose_name='PTT VOX Threshold (%)')),
                ('rx_attack_time',   models.FloatField(blank=True, null=True, verbose_name='RX Attack Time (ms)')),
                ('rx_release_time',  models.FloatField(blank=True, null=True, verbose_name='RX Release Time (ms)')),
                ('rx_voice_delay',   models.FloatField(blank=True, null=True, verbose_name='RX Voice Delay (ms)')),
                ('rx_vox_threshold', models.FloatField(blank=True, null=True, verbose_name='RX VOX Threshold (%)')),
                ('test_radio_master', models.CharField(blank=True, max_length=3, choices=[('OK','OK'),('NOK','NOK')], verbose_name='Test Fungsi Radio ke RoIP Master')),
                ('test_ping_master',  models.CharField(blank=True, max_length=3, choices=[('OK','OK'),('NOK','NOK')], verbose_name='Test Ping ke RoIP Master')),
                ('catatan', models.TextField(blank=True, default='')),
                ('maintenance', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='maintenanceroip', to='maintenance.maintenance')),
            ],
            options={'verbose_name': 'Maintenance RoIP'},
        ),
    ]
