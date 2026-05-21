from django.db import migrations, models


class Migration(migrations.Migration):
    """
    Alter help_text on fiberopticcore otdr_b fields.
    Depends on 0042 (branched in parallel with 0045).
    """

    dependencies = [
        ('devices', '0042_fiberopticcore_fungsi_b_keterangan_b'),
    ]

    operations = [
        migrations.AlterField(
            model_name='fiberopticcore',
            name='otdr_b_catatan',
            field=models.TextField(blank=True, null=True, verbose_name='OTDR B Catatan'),
        ),
        migrations.AlterField(
            model_name='fiberopticcore',
            name='otdr_b_tanggal',
            field=models.DateField(blank=True, null=True, verbose_name='OTDR B Tanggal Pengukuran'),
        ),
    ]
