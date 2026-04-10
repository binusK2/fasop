from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('maintenance', '0033_maintenanceroip'),
    ]

    operations = [
        migrations.AddField(
            model_name='maintenanceroip',
            name='bridge_conn_source',
            field=models.CharField(blank=True, max_length=100, verbose_name='Bridge Connection Source'),
        ),
        migrations.AddField(
            model_name='maintenanceroip',
            name='bridge_conn_destination',
            field=models.CharField(blank=True, max_length=100, verbose_name='Bridge Connection Destination'),
        ),
        migrations.AddField(
            model_name='maintenanceroip',
            name='dest_port_number',
            field=models.CharField(blank=True, max_length=20, verbose_name='Destination Port Number'),
        ),
        migrations.AddField(
            model_name='maintenanceroip',
            name='source_port_number',
            field=models.CharField(blank=True, max_length=20, verbose_name='Source Port Number'),
        ),
        migrations.AlterField(
            model_name='maintenanceroip',
            name='test_ping_master',
            field=models.FloatField(blank=True, null=True, verbose_name='Test Ping ke RoIP Master (ms)'),
        ),
    ]
