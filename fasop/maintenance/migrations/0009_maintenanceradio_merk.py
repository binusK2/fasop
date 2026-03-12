from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('maintenance', '0008_maintenanceradio'),
    ]

    operations = [
        migrations.AddField(
            model_name='maintenanceradio',
            name='merk_battery',
            field=models.CharField(blank=True, max_length=100, verbose_name='Merk Battery'),
        ),
        migrations.AddField(
            model_name='maintenanceradio',
            name='merk_power_supply',
            field=models.CharField(blank=True, max_length=100, verbose_name='Merk Power Supply'),
        ),
    ]
