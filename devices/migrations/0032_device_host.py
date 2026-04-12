from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('devices', '0031_deviceeviden'),
    ]

    operations = [
        migrations.AddField(
            model_name='device',
            name='host',
            field=models.ForeignKey(
                blank=True,
                help_text='Isi jika perangkat ini adalah VM di dalam server fisik',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='vm_children',
                to='devices.device',
                verbose_name='Host Server (untuk VM)',
            ),
        ),
    ]
