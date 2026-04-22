from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('devices', '0041_core_per_site_lambda_jarak'),
    ]

    operations = [
        migrations.AddField(
            model_name='fiberopticcore',
            name='fungsi_b',
            field=models.CharField(
                blank=True, null=True, max_length=200,
                verbose_name='Fungsi / Digunakan Untuk (Site B)',
            ),
        ),
        migrations.AddField(
            model_name='fiberopticcore',
            name='keterangan_b',
            field=models.TextField(blank=True, null=True, verbose_name='Catatan Site B'),
        ),
    ]
