import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('devices', '0051_merge_main_otdr_chains'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='branch',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='dispatchers',
                to='devices.branch',
                verbose_name='Branch',
                help_text='Untuk role Dispatcher — Branch yang dilayani. Pengujian hanya menampilkan lokasi dalam branch ini.',
            ),
        ),
    ]
