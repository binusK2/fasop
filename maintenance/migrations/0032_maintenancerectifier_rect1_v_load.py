from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('maintenance', '0031_maintenancesas'),
    ]

    operations = [
        migrations.AddField(
            model_name='maintenancerectifier',
            name='rect1_v_load',
            field=models.FloatField(blank=True, null=True, verbose_name='Rect1 V Load (V)'),
        ),
    ]
