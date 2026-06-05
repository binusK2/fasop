from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('maintenance', '0046_maintenancevoip_pengujian_perangkat'),
    ]

    operations = [
        migrations.AlterField(
            model_name='maintenancemux',
            name='psu1_status',
            field=models.CharField(
                blank=True, max_length=20,
                choices=[('OK', 'OK'), ('NOK', 'NOK'), ('Tidak Terpasang', 'Tidak Terpasang')],
            ),
        ),
        migrations.AlterField(
            model_name='maintenancemux',
            name='psu2_status',
            field=models.CharField(
                blank=True, max_length=20,
                choices=[('OK', 'OK'), ('NOK', 'NOK'), ('Tidak Terpasang', 'Tidak Terpasang')],
            ),
        ),
        migrations.AlterField(
            model_name='maintenancemux',
            name='fan_status',
            field=models.CharField(
                blank=True, max_length=20,
                choices=[('OK', 'OK'), ('NOK', 'NOK'), ('Tidak Terpasang', 'Tidak Terpasang')],
            ),
        ),
    ]
