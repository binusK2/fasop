from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('dokumentasi', '0001_initial'),
    ]

    operations = [
        # SettingRele — tambah tipe_setting & penyulang_bay
        migrations.AddField(
            model_name='settingrele',
            name='tipe_setting',
            field=models.CharField(
                blank=True, max_length=20,
                choices=[
                    ('oc_ground','OC Ground'), ('oc_phase','OC Phase'),
                    ('ef','Earth Fault (EF)'), ('differential','Differential'),
                    ('distance','Distance'), ('ds','Defense Scheme (DS)'),
                    ('master_trip','Master Trip'), ('ufls','UFLS'),
                    ('lainnya','Lainnya'),
                ],
                verbose_name='Tipe Setting',
            ),
        ),
        migrations.AddField(
            model_name='settingrele',
            name='penyulang_bay',
            field=models.CharField(blank=True, max_length=100, verbose_name='Penyulang / Bay'),
        ),
        # GambarDevice — tambah nomor_gambar & skala
        migrations.AddField(
            model_name='gambardevice',
            name='nomor_gambar',
            field=models.CharField(blank=True, max_length=100, verbose_name='Nomor Gambar'),
        ),
        migrations.AddField(
            model_name='gambardevice',
            name='skala',
            field=models.CharField(blank=True, max_length=30, verbose_name='Skala',
                                   help_text='Contoh: 1:100, NTS, A3'),
        ),
    ]
