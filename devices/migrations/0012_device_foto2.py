from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('devices', '0011_userprofile_display_name'),
    ]

    operations = [
        migrations.AddField(
            model_name='device',
            name='foto2',
            field=models.ImageField(blank=True, null=True, upload_to='device_photos/', verbose_name='Foto 2'),
        ),
    ]
