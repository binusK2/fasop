from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('gudang', '0002_alter_sparepart_options'),
        ('devices', '0049_komponenrusak_branch'),
    ]

    operations = [
        # branch di Sparepart
        migrations.AddField(
            model_name='sparepart',
            name='branch',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='sparepart_set',
                to='devices.branch',
                verbose_name='Branch / Gudang',
            ),
        ),
        # lokasi_penyimpanan sekarang opsional
        migrations.AlterField(
            model_name='sparepart',
            name='lokasi_penyimpanan',
            field=models.CharField(
                blank=True, max_length=150, verbose_name='Lokasi di Gudang',
                help_text='Contoh: Rak B3, Laci 2 Lemari Komponen',
            ),
        ),
        # sumber_komponen_rusak di MutasiSparepart
        migrations.AddField(
            model_name='mutasisparepart',
            name='sumber_komponen_rusak',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='mutasi_sparepart',
                to='devices.komponenrusak',
                verbose_name='Dari Komponen Rusak / Bongkar',
            ),
        ),
    ]
