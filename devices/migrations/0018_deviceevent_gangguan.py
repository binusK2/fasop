from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('devices', '0017_deviceevent'),
        ('gangguan', '0005_gangguan_public_token'),
    ]

    operations = [
        migrations.AddField(
            model_name='deviceevent',
            name='gangguan',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='perubahan_fisik',
                to='gangguan.gangguan',
                verbose_name='Terkait Gangguan',
            ),
        ),
    ]
