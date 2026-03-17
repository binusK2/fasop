from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('gangguan', '0002_gangguan_foto_eviden'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='GangguanLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('waktu_aksi', models.DateTimeField(verbose_name='Waktu Aksi')),
                ('keterangan', models.TextField(verbose_name='Keterangan Tindakan')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('gangguan', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                    related_name='log_entries', to='gangguan.gangguan')),
                ('dibuat_oleh', models.ForeignKey(blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='gangguan_log_entries',
                    to=settings.AUTH_USER_MODEL, verbose_name='Dicatat oleh')),
            ],
            options={
                'verbose_name': 'Log Tindak Lanjut',
                'ordering': ['waktu_aksi'],
            },
        ),
    ]
