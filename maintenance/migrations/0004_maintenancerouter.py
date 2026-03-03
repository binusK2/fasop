from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('maintenance', '0003_alter_maintenance_description_maintenanceplc'),
    ]

    operations = [
        migrations.CreateModel(
            name='MaintenanceRouter',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),

                # ── CHECKLIST FISIK ──────────────────────────────────────────
                ('kondisi_fisik',    models.CharField(max_length=3, choices=[('OK','OK'),('NOK','NOK')], blank=True, verbose_name='Kondisi Fisik Unit')),
                ('led_link',         models.CharField(max_length=3, choices=[('OK','OK'),('NOK','NOK')], blank=True, verbose_name='Indikator LED Link/Port')),
                ('kondisi_kabel',    models.CharField(max_length=3, choices=[('OK','OK'),('NOK','NOK')], blank=True, verbose_name='Kondisi Kabel & Konektor')),

                # ── PENGUKURAN ───────────────────────────────────────────────
                ('tegangan_input',   models.FloatField(null=True, blank=True, verbose_name='Tegangan Input (Volt)')),
                ('suhu_perangkat',   models.FloatField(null=True, blank=True, verbose_name='Suhu Perangkat (°C)')),
                ('cpu_load',         models.FloatField(null=True, blank=True, verbose_name='CPU Load (%)')),
                ('memory_usage',     models.FloatField(null=True, blank=True, verbose_name='Memory Usage (%)')),

                # ── INTERFACE / PORT ─────────────────────────────────────────
                ('jumlah_port_aktif',    models.PositiveSmallIntegerField(null=True, blank=True, verbose_name='Jumlah Port Aktif')),
                ('jumlah_port_total',    models.PositiveSmallIntegerField(null=True, blank=True, verbose_name='Jumlah Port Total')),
                ('status_routing',       models.CharField(max_length=3, choices=[('OK','OK'),('NOK','NOK')], blank=True, verbose_name='IP Address / Routing Status')),
                ('detail_port',          models.TextField(blank=True, verbose_name='Detail Status Port (opsional)')),

                # ── CATATAN ──────────────────────────────────────────────────
                ('catatan_tambahan',     models.TextField(blank=True, verbose_name='Catatan Tambahan')),

                ('maintenance', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    to='maintenance.maintenance'
                )),
            ],
            options={
                'verbose_name': 'Maintenance Router/Switch',
                'verbose_name_plural': 'Maintenance Router/Switch',
            },
        ),
    ]
