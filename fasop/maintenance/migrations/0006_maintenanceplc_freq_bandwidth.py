from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('maintenance', '0005_maintenancerouter_sfp'),
    ]

    operations = [
        migrations.AddField(
            model_name='maintenanceplc',
            name='freq_tx',
            field=models.FloatField(blank=True, null=True, verbose_name='Frequency TX (MHz)'),
        ),
        migrations.AddField(
            model_name='maintenanceplc',
            name='bandwidth_tx',
            field=models.FloatField(blank=True, null=True, verbose_name='Bandwidth TX (MHz)'),
        ),
        migrations.AddField(
            model_name='maintenanceplc',
            name='freq_rx',
            field=models.FloatField(blank=True, null=True, verbose_name='Frequency RX (MHz)'),
        ),
        migrations.AddField(
            model_name='maintenanceplc',
            name='bandwidth_rx',
            field=models.FloatField(blank=True, null=True, verbose_name='Bandwidth RX (MHz)'),
        ),
    ]
