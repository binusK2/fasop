from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('maintenance', '0009_maintenanceradio_merk'),
    ]

    operations = [
        migrations.CreateModel(
            name='MaintenanceVoIP',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('ip_address',         models.CharField(blank=True, max_length=50,  verbose_name='IP Address')),
                ('extension_number',   models.CharField(blank=True, max_length=50,  verbose_name='Extension Number')),
                ('sip_server_1',       models.CharField(blank=True, max_length=100, verbose_name='SIP Server 1')),
                ('sip_server_2',       models.CharField(blank=True, max_length=100, verbose_name='SIP Server 2')),
                ('suhu_ruangan',       models.FloatField(blank=True, null=True,     verbose_name='Suhu Ruangan (°C)')),
                ('kondisi_fisik',      models.CharField(blank=True, max_length=3, choices=[('OK', 'OK'), ('NOK', 'NOK')], verbose_name='Kondisi Fisik Perangkat')),
                ('ntp_server',         models.CharField(blank=True, max_length=3, choices=[('OK', 'OK'), ('NOK', 'NOK')], verbose_name='NTP Server')),
                ('webconfig',          models.CharField(blank=True, max_length=3, choices=[('OK', 'OK'), ('NOK', 'NOK')], verbose_name='Web Config')),
                ('ps_merk',            models.CharField(blank=True, max_length=100, verbose_name='Merk Power Supply')),
                ('ps_tegangan_input',  models.FloatField(blank=True, null=True,     verbose_name='Tegangan Input PSU (V)')),
                ('ps_status',          models.CharField(blank=True, max_length=3, choices=[('OK', 'OK'), ('NOK', 'NOK')], verbose_name='Status Power Supply')),
                ('catatan',            models.TextField(blank=True,                 verbose_name='Catatan')),
                ('maintenance', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    to='maintenance.maintenance'
                )),
            ],
            options={'verbose_name': 'Maintenance VoIP'},
        ),
    ]
