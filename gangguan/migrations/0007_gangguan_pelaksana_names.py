from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('gangguan', '0006_generate_public_tokens'),
    ]

    operations = [
        migrations.AddField(
            model_name='gangguan',
            name='pelaksana_names',
            field=models.JSONField(
                blank=True,
                default=list,
                verbose_name='Nama Pelaksana / PIC',
            ),
        ),
    ]
