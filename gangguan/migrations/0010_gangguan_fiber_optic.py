import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('devices', '0024_fiberoptic'),
        ('gangguan', '0009_gangguan_layanan_icon'),
    ]

    operations = [
        migrations.AddField(
            model_name='gangguan',
            name='tipe_gangguan',
            field=models.CharField(
                max_length=10,
                choices=[('device', 'Gangguan Device/Perangkat'), ('link', 'Gangguan Link/Fiber Optic')],
                default='device',
                verbose_name='Tipe Gangguan',
            ),
        ),
        migrations.AddField(
            model_name='gangguan',
            name='lokasi_b',
            field=models.CharField(
                max_length=150, blank=True, null=True,
                verbose_name='Lokasi B (Titik Ujung)',
                help_text='Titik ujung kedua — diisi untuk gangguan link/fiber optic',
            ),
        ),
        migrations.AddField(
            model_name='gangguan',
            name='fiber_optic',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='gangguan_terkait',
                to='devices.fiberoptic',
                verbose_name='Segmen Fiber Optic',
                help_text='Opsional — pilih segmen FO yang mengalami gangguan',
            ),
        ),
        migrations.AddField(
            model_name='gangguan',
            name='core_putus',
            field=models.CharField(
                max_length=100, blank=True, null=True,
                verbose_name='Core yang Putus',
                help_text='Misal: Core 1-2, Core 5, Semua core',
            ),
        ),
    ]
