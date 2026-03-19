from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('devices', '0014_device_status_operasi'),
    ]

    operations = [
        migrations.AddField(
            model_name='device',
            name='tahun_operasi',
            field=models.IntegerField(
                blank=True,
                null=True,
                verbose_name='Tahun Operasi',
                help_text='Tahun peralatan mulai beroperasi (contoh: 2019)',
            ),
        ),
    ]
