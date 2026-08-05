from django.db import migrations, models


class Migration(migrations.Migration):
    """
    Tambah `jenis` (induk point type OFDB: TELEMETERING/TELESIGNAL/RTU/MASTER/
    TELEKOMUNIKASI), path4/path5, dan label terbaca b1/b2/b3/elem ke tabel
    kinerja harian, plus index (jenis, tanggal) untuk filter halaman.
    """

    dependencies = [
        ('up2bmakassar', '0003_remotecontrol'),
    ]

    operations = [
        migrations.AddField(
            model_name='kinerjaanalogharian',
            name='jenis',
            field=models.CharField(blank=True, db_index=True, default='', max_length=50),
        ),
        migrations.AddField(
            model_name='kinerjadigitalharian',
            name='jenis',
            field=models.CharField(blank=True, db_index=True, default='', max_length=50),
        ),
    ] + [
        migrations.AddField(
            model_name=model,
            name=field,
            field=models.CharField(blank=True, default='', max_length=100),
        )
        for model in ('kinerjaanalogharian', 'kinerjadigitalharian')
        for field in ('path4', 'path5', 'b1', 'b2', 'b3', 'elem')
    ] + [
        migrations.AddIndex(
            model_name='kinerjaanalogharian',
            index=models.Index(fields=['jenis', 'tanggal'], name='up2b_kin_ana_jenis_tgl_idx'),
        ),
        migrations.AddIndex(
            model_name='kinerjadigitalharian',
            index=models.Index(fields=['jenis', 'tanggal'], name='up2b_kin_dig_jenis_tgl_idx'),
        ),
    ]
