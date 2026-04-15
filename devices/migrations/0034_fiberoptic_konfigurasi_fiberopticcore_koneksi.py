from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('devices', '0033_fiberoptic_konektor_ab_foto'),
    ]

    operations = [
        migrations.AddField(
            model_name='fiberoptic',
            name='konfigurasi',
            field=models.CharField(
                blank=True, null=True, max_length=20,
                choices=[('lurus', 'Lurus (Straight)'), ('crossing', 'Crossing'), ('campuran', 'Campuran')],
                verbose_name='Konfigurasi Core',
                help_text='Lurus: core A1→B1; Crossing: core A1→B lain',
            ),
        ),
        migrations.AddField(
            model_name='fiberopticcore',
            name='koneksi_a',
            field=models.CharField(
                blank=True, null=True, max_length=200,
                verbose_name='Koneksi Site A',
                help_text='Perangkat/port yang terhubung di Site A (misal: ODF-1 port 3)',
            ),
        ),
        migrations.AddField(
            model_name='fiberopticcore',
            name='koneksi_b',
            field=models.CharField(
                blank=True, null=True, max_length=200,
                verbose_name='Koneksi Site B',
                help_text='Perangkat/port yang terhubung di Site B (misal: Switch GI Barru eth1)',
            ),
        ),
    ]
