from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('gangguan', '0003_gangguanlog'),
    ]

    operations = [
        migrations.AlterField(
            model_name='gangguan',
            name='tindak_lanjut',
            field=models.TextField(blank=True, verbose_name='Tindak Lanjut'),
        ),
    ]
