from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('maintenance', '0004_maintenancerouter'),
    ]

    operations = [
        migrations.AddField(
            model_name='maintenancerouter',
            name='jumlah_sfp_port',
            field=models.PositiveSmallIntegerField(blank=True, null=True, verbose_name='Jumlah SFP Port'),
        ),
        migrations.AddField(
            model_name='maintenancerouter',
            name='sfp_port_data',
            field=models.TextField(blank=True, verbose_name='Data SFP Port (JSON)'),
        ),
    ]
