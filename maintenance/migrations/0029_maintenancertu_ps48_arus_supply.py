from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('maintenance', '0028_maintenancertu'),
    ]

    operations = [
        migrations.AddField(
            model_name='maintenancertu',
            name='ps48_arus_supply',
            field=models.FloatField(blank=True, null=True, verbose_name='48V Arus Supply (A)'),
        ),
    ]
