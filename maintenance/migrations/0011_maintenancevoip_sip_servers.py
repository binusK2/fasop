from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('maintenance', '0010_maintenancevoip'),
    ]

    operations = [
        migrations.AddField(
            model_name='maintenancevoip',
            name='sip_server_1',
            field=models.CharField(blank=True, max_length=100, verbose_name='SIP Server 1'),
        ),
        migrations.AddField(
            model_name='maintenancevoip',
            name='sip_server_2',
            field=models.CharField(blank=True, max_length=100, verbose_name='SIP Server 2'),
        ),
    ]
