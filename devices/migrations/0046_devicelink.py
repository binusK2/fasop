from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('devices', '0045_add_komponen_baru_fields_and_komponen_rusak'),
    ]

    operations = [
        migrations.CreateModel(
            name='DeviceLink',
            fields=[
                ('id',         models.AutoField(auto_created=True, primary_key=True, serialize=False)),
                ('tipe',       models.CharField(
                                   max_length=20,
                                   choices=[
                                       ('fiber',      'Fiber Optik'),
                                       ('radio',      'Radio / MW'),
                                       ('opgw',       'OPGW'),
                                       ('pilot_wire', 'Pilot Wire'),
                                       ('lainnya',    'Lainnya'),
                                   ],
                                   default='fiber',
                                   verbose_name='Tipe Koneksi',
                               )),
                ('label',      models.CharField(blank=True, max_length=120, verbose_name='Label',
                                   help_text='Kosongkan untuk otomatis "NamaA → NamaB"')),
                ('aktif',      models.BooleanField(default=True, verbose_name='Aktif')),
                ('keterangan', models.TextField(blank=True, verbose_name='Keterangan')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('device_a',   models.ForeignKey(
                                   on_delete=django.db.models.deletion.CASCADE,
                                   related_name='link_dari',
                                   to='devices.device',
                                   verbose_name='Perangkat A',
                               )),
                ('device_b',   models.ForeignKey(
                                   on_delete=django.db.models.deletion.CASCADE,
                                   related_name='link_ke',
                                   to='devices.device',
                                   verbose_name='Perangkat B',
                               )),
            ],
            options={
                'verbose_name':        'Koneksi Perangkat',
                'verbose_name_plural': 'Koneksi Perangkat',
                'ordering':            ['device_a__lokasi', 'device_a__nama'],
            },
        ),
    ]
