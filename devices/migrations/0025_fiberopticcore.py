import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('devices', '0024_fiberoptic'),
    ]

    operations = [
        migrations.CreateModel(
            name='FiberOpticCore',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nomor_core', models.PositiveIntegerField(verbose_name='Nomor Core')),
                ('fungsi', models.CharField(
                    blank=True, null=True, max_length=200,
                    verbose_name='Fungsi / Digunakan Untuk',
                    help_text='Misal: Link SCADA GI Tello–Barru, VoIP Kantor, Spare',
                )),
                ('status', models.CharField(
                    max_length=20, default='spare',
                    choices=[
                        ('aktif',      'Aktif / Digunakan'),
                        ('spare',      'Spare / Cadangan'),
                        ('rusak',      'Rusak / Putus'),
                        ('tidak_aktif','Tidak Aktif'),
                    ],
                    verbose_name='Status Core',
                )),
                ('otdr_jarak_km', models.DecimalField(
                    blank=True, null=True, max_digits=8, decimal_places=3,
                    verbose_name='OTDR Jarak (km)',
                )),
                ('otdr_redaman_db', models.DecimalField(
                    blank=True, null=True, max_digits=6, decimal_places=3,
                    verbose_name='OTDR Redaman (dB)',
                )),
                ('otdr_redaman_per_km', models.DecimalField(
                    blank=True, null=True, max_digits=5, decimal_places=3,
                    verbose_name='Redaman per km (dB/km)',
                )),
                ('otdr_tanggal', models.DateField(blank=True, null=True, verbose_name='Tanggal Pengukuran OTDR')),
                ('otdr_catatan', models.TextField(blank=True, null=True, verbose_name='Catatan OTDR')),
                ('keterangan', models.TextField(blank=True, null=True, verbose_name='Keterangan')),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('fiber_optic', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='cores',
                    to='devices.fiberoptic',
                    verbose_name='Segmen FO',
                )),
            ],
            options={
                'verbose_name': 'Core Fiber Optic',
                'verbose_name_plural': 'Core Fiber Optic',
                'ordering': ['fiber_optic', 'nomor_core'],
            },
        ),
        migrations.AlterUniqueTogether(
            name='fiberopticcore',
            unique_together={('fiber_optic', 'nomor_core')},
        ),
    ]
