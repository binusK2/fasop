import secrets
from django.db import migrations, models


def generate_tokens(apps, schema_editor):
    Device = apps.get_model('devices', 'Device')
    for d in Device.objects.filter(public_token__isnull=True):
        d.public_token = secrets.token_urlsafe(20)
        d.save(update_fields=['public_token'])


class Migration(migrations.Migration):

    dependencies = [
        ('devices', '0018_deviceevent_gangguan'),
    ]

    operations = [
        migrations.AddField(
            model_name='device',
            name='public_token',
            field=models.CharField(
                blank=True, max_length=40, null=True, unique=True,
                verbose_name='Token Publik QR',
            ),
        ),
        migrations.RunPython(generate_tokens, migrations.RunPython.noop),
    ]
