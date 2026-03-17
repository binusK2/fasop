from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('gangguan', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='gangguan',
            name='foto_eviden1',
            field=models.ImageField(blank=True, null=True, upload_to='gangguan_eviden/', verbose_name='Foto Eviden 1'),
        ),
        migrations.AddField(
            model_name='gangguan',
            name='foto_eviden2',
            field=models.ImageField(blank=True, null=True, upload_to='gangguan_eviden/', verbose_name='Foto Eviden 2'),
        ),
        migrations.AddField(
            model_name='gangguan',
            name='foto_eviden3',
            field=models.ImageField(blank=True, null=True, upload_to='gangguan_eviden/', verbose_name='Foto Eviden 3'),
        ),
    ]
