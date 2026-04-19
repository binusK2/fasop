from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('devices', '0036_fiberopticcore_status_ab'),
    ]

    operations = [
        migrations.AddField(
            model_name='fiberoptic',
            name='public_token',
            field=models.CharField(
                blank=True, max_length=40, null=True, unique=True,
                verbose_name='Token Publik QR',
            ),
        ),
    ]
