from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('devices', '0015_device_tahun_operasi'),
    ]

    operations = [
        migrations.CreateModel(
            name='HISnapshot',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('score', models.IntegerField(verbose_name='Skor HI')),
                ('kategori', models.CharField(max_length=20, verbose_name='Kategori')),
                ('breakdown', models.JSONField(default=list, verbose_name='Breakdown Faktor')),
                ('bulan', models.PositiveSmallIntegerField(verbose_name='Bulan')),
                ('tahun', models.PositiveSmallIntegerField(verbose_name='Tahun')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('device', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='hi_snapshots',
                    to='devices.device',
                )),
            ],
            options={
                'verbose_name': 'Snapshot Health Index',
                'verbose_name_plural': 'Snapshot Health Index',
                'ordering': ['-tahun', '-bulan'],
                'unique_together': {('device', 'bulan', 'tahun')},
            },
        ),
    ]
