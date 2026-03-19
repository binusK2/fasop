from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('devices', '0015_device_tahun_operasi'),
    ]

    operations = [
        migrations.CreateModel(
            name='Notifikasi',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('tipe', models.CharField(max_length=30, choices=[('hi_rendah','Health Index Rendah'),('hi_turun','HI Turun Drastis'),('maintenance_overdue','Maintenance Overdue'),('gangguan_lama','Gangguan Terlalu Lama')])),
                ('judul', models.CharField(max_length=200)),
                ('pesan', models.TextField()),
                ('level', models.CharField(max_length=10, choices=[('danger','Danger'),('warning','Warning'),('info','Info')], default='warning')),
                ('url', models.CharField(max_length=200, blank=True)),
                ('is_read', models.BooleanField(default=False, verbose_name='Sudah Dibaca')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('read_at', models.DateTimeField(null=True, blank=True)),
                ('device', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='notifikasi', to='devices.device')),
            ],
            options={
                'verbose_name': 'Notifikasi',
                'verbose_name_plural': 'Notifikasi',
                'ordering': ['-created_at'],
            },
        ),
    ]
