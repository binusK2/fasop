from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('devices', '0037_fiberoptic_public_token'),
    ]

    operations = [
        migrations.AddField(
            model_name='device',
            name='wiring_json',
            field=models.JSONField(blank=True, null=True, verbose_name='Wiring Diagram Data'),
        ),
        migrations.AddField(
            model_name='device',
            name='wiring_img',
            field=models.ImageField(blank=True, null=True, upload_to='wiring/', verbose_name='Wiring Diagram Image'),
        ),
    ]
