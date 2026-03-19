import secrets
from django.db import migrations


def generate_missing_tokens(apps, schema_editor):
    Gangguan = apps.get_model('gangguan', 'Gangguan')
    for g in Gangguan.objects.filter(public_token__isnull=True):
        g.public_token = secrets.token_urlsafe(20)
        g.save(update_fields=['public_token'])


class Migration(migrations.Migration):

    dependencies = [
        ('gangguan', '0005_gangguan_public_token'),
    ]

    operations = [
        migrations.RunPython(generate_missing_tokens, migrations.RunPython.noop),
    ]
