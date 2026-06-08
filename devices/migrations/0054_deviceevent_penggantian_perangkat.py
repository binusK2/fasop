from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('devices', '0053_itembongkar_deviceevent_updates'),
    ]

    operations = [
        migrations.AddField(
            model_name='deviceevent',
            name='perangkat_pengganti',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='menggantikan_event',
                to='devices.device',
                verbose_name='Perangkat Pengganti (baru)',
            ),
        ),
        migrations.AlterField(
            model_name='deviceevent',
            name='tipe',
            field=models.CharField(
                choices=[
                    ('relokasi',              'Relokasi / Pindah Lokasi'),
                    ('penggantian',           'Penggantian Komponen'),
                    ('penggantian_perangkat', 'Penggantian Perangkat'),
                    ('pembongkaran',          'Pembongkaran'),
                    ('pemasangan',            'Pemasangan Kembali'),
                    ('penambahan',            'Penambahan Komponen'),
                    ('modifikasi',            'Modifikasi Konfigurasi'),
                ],
                max_length=20, verbose_name='Tipe Kejadian',
            ),
        ),
    ]
