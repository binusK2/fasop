from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import maintenance.models


class Migration(migrations.Migration):

    dependencies = [
        ('maintenance', '0036_maintenanceups'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='BeritaAcaraRecord',
            fields=[
                ('id',         models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('jenis',      models.CharField(choices=[('pemasangan', 'Pemasangan'), ('pembongkaran', 'Pembongkaran'), ('penggantian', 'Penggantian')], max_length=20)),
                ('nomor_ba',   models.CharField(blank=True, max_length=200)),
                ('tanggal',    models.DateField()),
                ('pelaksana',  models.CharField(max_length=200)),
                ('nip',        models.CharField(blank=True, max_length=100)),
                ('jabatan',    models.CharField(blank=True, max_length=200)),
                ('catatan',    models.TextField(blank=True)),
                ('rows_data',  models.JSONField(default=list)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='ba_records', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Berita Acara Record',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='BeritaAcaraEviden',
            fields=[
                ('id',      models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('gambar',  models.ImageField(upload_to=maintenance.models.ba_eviden_upload)),
                ('catatan', models.CharField(blank=True, max_length=500)),
                ('urutan',  models.PositiveSmallIntegerField(default=0)),
                ('ba',      models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='evidens', to='maintenance.beritaacararecord')),
            ],
            options={
                'ordering': ['urutan'],
            },
        ),
    ]
