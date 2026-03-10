from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('devices', '0006_alter_device_ip_address'),
    ]

    operations = [
        migrations.AddField(
            model_name='device',
            name='spesifikasi',
            field=models.JSONField(blank=True, default=dict, null=True),
        ),
    ]
