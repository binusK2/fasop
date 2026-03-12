from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('maintenance', '0007_alter_maintenance_options_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='MaintenanceRadio',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('suhu_ruangan', models.FloatField(blank=True, null=True, verbose_name='Suhu Ruangan (°C)')),
                ('kebersihan', models.CharField(blank=True, choices=[('Bersih', 'Bersih'), ('Kotor', 'Kotor')], max_length=10)),
                ('lampu_penerangan', models.CharField(blank=True, choices=[('Menyala', 'Menyala'), ('Tidak Menyala', 'Tidak Menyala'), ('Redup', 'Redup'), ('Tidak Ada', 'Tidak Ada')], max_length=15)),
                ('ada_radio', models.CharField(blank=True, choices=[('OK', 'OK'), ('NOK', 'NOK')], max_length=3, verbose_name='Radio')),
                ('ada_battery', models.CharField(blank=True, choices=[('OK', 'OK'), ('NOK', 'NOK')], max_length=3, verbose_name='Battery')),
                ('ada_power_supply', models.CharField(blank=True, choices=[('OK', 'OK'), ('NOK', 'NOK')], max_length=3, verbose_name='Power Supply')),
                ('jenis_antena', models.CharField(blank=True, choices=[('Directional', 'Directional'), ('Bidirectional', 'Bidirectional')], max_length=15, verbose_name='Jenis Antena')),
                ('swr', models.CharField(blank=True, choices=[('<1.5', '< 1,5 (Baik)'), ('>1.5', '> 1,5 (Buruk)')], max_length=5, verbose_name='SWR')),
                ('power_tx', models.FloatField(blank=True, null=True, verbose_name='Power TX (W)')),
                ('tegangan_battery', models.FloatField(blank=True, null=True, verbose_name='Tegangan Battery (V)')),
                ('tegangan_psu', models.FloatField(blank=True, null=True, verbose_name='Tegangan Power Supply (V)')),
                ('frekuensi_tx', models.FloatField(blank=True, null=True, verbose_name='Frekuensi TX / Tone (MHz)')),
                ('frekuensi_rx', models.FloatField(blank=True, null=True, verbose_name='Frekuensi RX / Tone (MHz)')),
                ('catatan', models.TextField(blank=True, verbose_name='Catatan')),
                ('maintenance', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, to='maintenance.maintenance')),
            ],
            options={'verbose_name': 'Maintenance Radio'},
        ),
    ]
