import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('devices', '0023_deviceevent_komponen_terkait'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='FiberOptic',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nama', models.CharField(max_length=200, verbose_name='Nama Segmen', help_text='Misal: Link FO GI Tello – GI Barru')),
                ('lokasi_a', models.CharField(max_length=150, verbose_name='Titik A (Asal)')),
                ('lokasi_b', models.CharField(max_length=150, verbose_name='Titik B (Tujuan)')),
                ('tipe_kabel', models.CharField(
                    blank=True, null=True, max_length=20,
                    choices=[
                        ('G.652D','G.652D — Single Mode Standard'),
                        ('G.652C','G.652C — Single Mode Low Water Peak'),
                        ('G.655','G.655 — Non-Zero Dispersion Shifted'),
                        ('G.657A1','G.657A1 — Bend Insensitive'),
                        ('G.657A2','G.657A2 — Bend Insensitive Enhanced'),
                        ('OM3','OM3 — Multi Mode 50/125'),
                        ('OM4','OM4 — Multi Mode 50/125 Enhanced'),
                        ('lainnya','Lainnya'),
                    ],
                    verbose_name='Tipe Kabel',
                )),
                ('tipe_konektor', models.CharField(
                    blank=True, null=True, max_length=20,
                    choices=[
                        ('SC','SC (Subscriber Connector)'),
                        ('LC','LC (Lucent Connector)'),
                        ('FC','FC (Ferrule Connector)'),
                        ('ST','ST (Straight Tip)'),
                        ('MTP','MTP/MPO (Multi-fiber Push On)'),
                        ('E2000','E2000'),
                        ('lainnya','Lainnya'),
                    ],
                    verbose_name='Tipe Konektor',
                )),
                ('jumlah_core', models.PositiveIntegerField(blank=True, null=True, verbose_name='Jumlah Core')),
                ('panjang_km', models.DecimalField(blank=True, null=True, max_digits=8, decimal_places=2, verbose_name='Panjang (km)')),
                ('tahun_pasang', models.PositiveIntegerField(blank=True, null=True, verbose_name='Tahun Pemasangan')),
                ('status', models.CharField(
                    max_length=20, default='baik',
                    choices=[
                        ('baik','Baik'),
                        ('gangguan','Gangguan'),
                        ('dalam_perbaikan','Dalam Perbaikan'),
                        ('tidak_aktif','Tidak Aktif'),
                    ],
                    verbose_name='Status',
                )),
                ('keterangan', models.TextField(blank=True, null=True, verbose_name='Keterangan')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_by', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='fiber_dibuat',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='Dibuat Oleh',
                )),
            ],
            options={
                'verbose_name': 'Fiber Optic',
                'verbose_name_plural': 'Fiber Optic',
                'ordering': ['nama'],
            },
        ),
    ]
