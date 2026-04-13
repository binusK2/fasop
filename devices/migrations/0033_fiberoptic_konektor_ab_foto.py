from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('devices', '0032_device_host'),
    ]

    operations = [
        migrations.AddField(
            model_name='fiberoptic',
            name='tipe_konektor_a',
            field=models.CharField(
                blank=True, null=True, max_length=20,
                choices=[('SC','SC (subscriber Connector)'),('LC','LC (Lucent Connector)'),('FC','FC (Ferrule Connector)'),('lainnya','Lainnya')],
                verbose_name='Tipe Konektor Site A',
            ),
        ),
        migrations.AddField(
            model_name='fiberoptic',
            name='tipe_konektor_b',
            field=models.CharField(
                blank=True, null=True, max_length=20,
                choices=[('SC','SC (subscriber Connector)'),('LC','LC (Lucent Connector)'),('FC','FC (Ferrule Connector)'),('lainnya','Lainnya')],
                verbose_name='Tipe Konektor Site B',
            ),
        ),
        migrations.AddField(
            model_name='fiberoptic',
            name='foto_site_a',
            field=models.ImageField(
                blank=True, null=True,
                upload_to='fiber_optic/foto/',
                verbose_name='Foto Site A',
            ),
        ),
        migrations.AddField(
            model_name='fiberoptic',
            name='foto_site_b',
            field=models.ImageField(
                blank=True, null=True,
                upload_to='fiber_optic/foto/',
                verbose_name='Foto Site B',
            ),
        ),
    ]
