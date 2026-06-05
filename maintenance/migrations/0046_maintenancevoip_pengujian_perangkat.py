from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('maintenance', '0045_merge_teleproteksi_main'),
    ]

    operations = [
        migrations.AddField(
            model_name='maintenancevoip',
            name='pengujian_perangkat',
            field=models.CharField(
                blank=True, max_length=15,
                choices=[('Normal', 'Normal'), ('Putus-Putus', 'Putus-Putus'), ('Gangguan', 'Gangguan')],
                verbose_name='Pengujian Perangkat',
            ),
        ),
    ]
