from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('jadwal', '0001_initial'),
    ]

    operations = [
        # Hapus unique_together lama
        migrations.AlterUniqueTogether(
            name='jadwalkunjungan',
            unique_together=set(),
        ),
        # Tambah field minggu_rencana
        migrations.AddField(
            model_name='jadwalkunjungan',
            name='minggu_rencana',
            field=models.PositiveSmallIntegerField(
                default=0,
                verbose_name='Minggu Rencana',
                choices=[(0, 'Semua Minggu'), (1, 'Minggu 1'), (2, 'Minggu 2'), (3, 'Minggu 3'), (4, 'Minggu 4')],
            ),
        ),
        # Pasang unique_together baru
        migrations.AlterUniqueTogether(
            name='jadwalkunjungan',
            unique_together={('lokasi', 'bulan_rencana', 'tahun_rencana', 'minggu_rencana')},
        ),
        # Update ordering
        migrations.AlterModelOptions(
            name='jadwalkunjungan',
            options={
                'ordering': ['tahun_rencana', 'bulan_rencana', 'minggu_rencana', 'lokasi'],
                'verbose_name': 'Jadwal Kunjungan',
                'verbose_name_plural': 'Jadwal Kunjungan',
            },
        ),
    ]
