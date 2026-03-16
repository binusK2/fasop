from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('maintenance', '0019_alter_maintenance_date'),
    ]

    operations = [
        migrations.AddField(
            model_name='maintenance',
            name='pelaksana_names',
            field=models.JSONField(
                blank=True,
                default=list,
                verbose_name='Nama Pelaksana',
            ),
        ),
    ]
