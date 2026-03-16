from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('maintenance', '0020_maintenance_pelaksana_names'),
    ]

    operations = [
        migrations.AddField(
            model_name='maintenance',
            name='catatan_am',
            field=models.TextField(blank=True, default='', verbose_name='Catatan Asisten Manager'),
        ),
    ]
