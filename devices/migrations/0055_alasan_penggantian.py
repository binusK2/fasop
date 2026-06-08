from django.db import migrations, models


ALASAN_CHOICES = [
    ('rusak',     'Rusak / Tidak Berfungsi'),
    ('kinerja',   'Kinerja Menurun'),
    ('lifetime',  'Habis Masa Pakai'),
    ('preventif', 'Pemeliharaan Preventif'),
    ('lainnya',   'Lainnya'),
]


class Migration(migrations.Migration):

    dependencies = [
        ('devices', '0054_deviceevent_penggantian_perangkat'),
    ]

    operations = [
        migrations.AddField(
            model_name='deviceevent',
            name='alasan_penggantian',
            field=models.CharField(
                blank=True, max_length=20,
                choices=ALASAN_CHOICES,
                verbose_name='Alasan Penggantian / Pembongkaran',
            ),
        ),
        migrations.AddField(
            model_name='komponenrusak',
            name='alasan_penggantian',
            field=models.CharField(
                blank=True, max_length=20,
                choices=ALASAN_CHOICES,
                verbose_name='Alasan Penggantian',
            ),
        ),
        migrations.AddField(
            model_name='itembongkar',
            name='alasan_penggantian',
            field=models.CharField(
                blank=True, max_length=20,
                choices=ALASAN_CHOICES,
                verbose_name='Alasan Pembongkaran / Penggantian',
            ),
        ),
    ]
