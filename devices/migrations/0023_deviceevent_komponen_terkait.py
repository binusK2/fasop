import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('devices', '0022_userprofile_force_password_change'),
    ]

    operations = [
        migrations.AddField(
            model_name='deviceevent',
            name='komponen_terkait',
            field=models.ForeignKey(
                blank=True,
                help_text='Opsional — pilih komponen spesifik dari database',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='device_events',
                to='devices.devicecomponent',
                verbose_name='Komponen Terkait',
            ),
        ),
    ]
