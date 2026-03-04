from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('maintenance', '0015_remove_rect2_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='maintenancerectifier',
            name='catatan',
            field=models.TextField(blank=True, default=''),
        ),
    ]
