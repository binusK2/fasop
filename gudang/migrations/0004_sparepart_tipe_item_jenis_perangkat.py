from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('gudang', '0003_sparepart_branch_mutasi_sumber'),
        ('devices', '0049_komponenrusak_branch'),
    ]

    operations = [
        migrations.AddField(
            model_name='sparepart',
            name='tipe_item',
            field=models.CharField(
                choices=[('material', 'Material / Komponen'), ('peralatan', 'Peralatan')],
                default='material',
                max_length=20,
                verbose_name='Tipe Item',
            ),
        ),
        migrations.AddField(
            model_name='sparepart',
            name='jenis_perangkat',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='sparepart_set',
                to='devices.devicetype',
                verbose_name='Jenis Perangkat',
                help_text='Diisi jika tipe item adalah Peralatan',
            ),
        ),
        migrations.AlterField(
            model_name='sparepart',
            name='nama',
            field=models.CharField(max_length=150, verbose_name='Nama'),
        ),
        migrations.AlterField(
            model_name='sparepart',
            name='kategori',
            field=models.CharField(
                blank=True, max_length=100, verbose_name='Kategori',
                help_text='Contoh: SFP, Kabel, Baterai, Power Supply',
            ),
        ),
    ]
