from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import common_enemy.models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('devices', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='CommonEnemy',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nomor_ce', models.CharField(editable=False, max_length=30, unique=True, verbose_name='Nomor CE')),
                ('status', models.CharField(
                    choices=[('open', 'Open'), ('in_progress', 'In Progress'), ('resolved', 'Resolved'), ('closed', 'Closed')],
                    default='open', max_length=20, verbose_name='Status'
                )),
                ('tingkat_keparahan', models.CharField(
                    choices=[('kritis', 'Kritis'), ('tinggi', 'Tinggi'), ('sedang', 'Sedang'), ('rendah', 'Rendah')],
                    default='sedang', max_length=10, verbose_name='Tingkat Keparahan'
                )),
                ('sumber_laporan', models.CharField(
                    choices=[('operator', 'Laporan Operator'), ('dispatcher', 'Dispatcher'), ('surat', 'Surat / Disposisi'), ('inspeksi', 'Temuan Inspeksi'), ('lainnya', 'Lainnya')],
                    default='operator', max_length=20, verbose_name='Sumber Laporan'
                )),
                ('kategori', models.CharField(
                    choices=[('scada', 'SCADA'), ('telkom', 'Telekomunikasi'), ('prosis', 'Proteksi & Sistem'), ('lainnya', 'Lainnya')],
                    default='telkom', max_length=20, verbose_name='Kategori / Bidang'
                )),
                ('site', models.CharField(max_length=150, verbose_name='Site / Lokasi')),
                ('tanggal_laporan', models.DateTimeField(verbose_name='Tanggal & Jam Laporan')),
                ('tanggal_resolved', models.DateTimeField(blank=True, null=True, verbose_name='Tanggal & Jam Resolved')),
                ('deskripsi_masalah', models.TextField(verbose_name='Deskripsi Masalah')),
                ('tindak_lanjut', models.TextField(blank=True, verbose_name='Tindak Lanjut')),
                ('catatan_penutupan', models.TextField(blank=True, verbose_name='Catatan Penutupan')),
                ('pelaksana_names', models.JSONField(blank=True, default=list, verbose_name='Nama Pelaksana / PIC')),
                ('foto_eviden1', models.ImageField(blank=True, null=True, upload_to=common_enemy.models.ce_eviden1_upload, verbose_name='Foto Eviden 1')),
                ('foto_eviden2', models.ImageField(blank=True, null=True, upload_to=common_enemy.models.ce_eviden2_upload, verbose_name='Foto Eviden 2')),
                ('foto_eviden3', models.ImageField(blank=True, null=True, upload_to=common_enemy.models.ce_eviden3_upload, verbose_name='Foto Eviden 3')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Dibuat Pada')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Diupdate Pada')),
                ('created_by', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='ce_dibuat',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='Dilaporkan oleh'
                )),
                ('peralatan', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='common_enemy_terkait',
                    to='devices.device',
                    verbose_name='Peralatan Terdampak'
                )),
                ('sub_kategori', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='common_enemy_terkait',
                    to='devices.devicetype',
                    verbose_name='Sub Kategori (Jenis Peralatan)'
                )),
            ],
            options={
                'verbose_name': 'Common Enemy',
                'verbose_name_plural': 'Common Enemy',
                'ordering': ['-tanggal_laporan'],
            },
        ),
        migrations.CreateModel(
            name='CommonEnemyLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('waktu_aksi', models.DateTimeField(verbose_name='Waktu Aksi')),
                ('keterangan', models.TextField(verbose_name='Keterangan Tindakan')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('common_enemy', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='log_entries',
                    to='common_enemy.commonenemy'
                )),
                ('dibuat_oleh', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='ce_log_entries',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='Dicatat oleh'
                )),
            ],
            options={
                'verbose_name': 'Log Tindak Lanjut CE',
                'ordering': ['waktu_aksi'],
            },
        ),
    ]
