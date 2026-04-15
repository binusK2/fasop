from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('devices', '0035_fiberopticcore_otdr_b'),
    ]

    operations = [
        migrations.AddField(
            model_name='fiberopticcore',
            name='status_a',
            field=models.CharField(
                max_length=20, default='spare',
                choices=[('aktif','Aktif / Digunakan'),('spare','Spare / Cadangan'),('rusak','Rusak / Putus'),('tidak_aktif','Tidak Aktif')],
                verbose_name='Status Core Site A',
            ),
        ),
        migrations.AddField(
            model_name='fiberopticcore',
            name='status_b',
            field=models.CharField(
                max_length=20, default='spare',
                choices=[('aktif','Aktif / Digunakan'),('spare','Spare / Cadangan'),('rusak','Rusak / Putus'),('tidak_aktif','Tidak Aktif')],
                verbose_name='Status Core Site B',
            ),
        ),
    ]
