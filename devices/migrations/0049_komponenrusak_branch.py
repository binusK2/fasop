from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('devices', '0048_branch'),
    ]

    operations = [
        migrations.AddField(
            model_name='komponenrusak',
            name='branch',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='komponen_rusak_set',
                to='devices.branch',
                verbose_name='Disimpan di Branch',
            ),
        ),
    ]
