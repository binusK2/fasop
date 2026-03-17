from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('devices', '0013_sitelocation'),
    ]

    operations = [
        migrations.AddField(
            model_name='device',
            name='status_operasi',
            field=models.CharField(
                max_length=20,
                choices=[('operasi', 'Operasi'), ('tidak_operasi', 'Tidak Operasi')],
                default='operasi',
                verbose_name='Status Operasi',
            ),
        ),
    ]
