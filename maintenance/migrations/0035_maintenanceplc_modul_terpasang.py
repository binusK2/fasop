from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('maintenance', '0034_maintenanceroip_bridge_ping_ms'),
    ]

    operations = [
        migrations.AddField(
            model_name='maintenanceplc',
            name='modul_terpasang',
            field=models.JSONField(blank=True, default=list, verbose_name='Modul Terpasang'),
        ),
    ]
