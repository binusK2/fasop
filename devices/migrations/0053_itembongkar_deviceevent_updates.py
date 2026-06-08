from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('devices', '0052_userprofile_branch'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # 1. Buat tabel ItemBongkar dulu (tanpa FK ke DeviceEvent dulu)
        migrations.CreateModel(
            name='ItemBongkar',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False)),
                ('tipe', models.CharField(choices=[('perangkat', 'Perangkat'), ('komponen', 'Komponen')], max_length=10, verbose_name='Tipe Item')),
                ('nama', models.CharField(max_length=150, verbose_name='Nama')),
                ('merk', models.CharField(blank=True, max_length=100, verbose_name='Merk')),
                ('model_tipe', models.CharField(blank=True, max_length=100, verbose_name='Model / Tipe')),
                ('serial_number', models.CharField(blank=True, max_length=100, verbose_name='Serial Number')),
                ('lokasi_penyimpanan', models.CharField(blank=True, max_length=200, verbose_name='Lokasi Spesifik di Gudang')),
                ('tanggal_bongkar', models.DateField(verbose_name='Tanggal Pembongkaran')),
                ('status', models.CharField(choices=[('di_gudang', 'Di Gudang'), ('dipasang_kembali', 'Dipasang Kembali'), ('dibuang', 'Dibuang / Dihapus')], default='di_gudang', max_length=20, verbose_name='Status')),
                ('catatan', models.TextField(blank=True, verbose_name='Catatan')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('branch', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='item_bongkar', to='devices.branch', verbose_name='Disimpan di Branch')),
                ('komponen_terkait', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='item_bongkar', to='devices.devicecomponent', verbose_name='Referensi Komponen')),
                ('device_asal', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='item_bongkar', to='devices.device', verbose_name='Perangkat Asal')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='item_bongkar_dicatat', to=settings.AUTH_USER_MODEL, verbose_name='Dicatat oleh')),
                # FK ke DeviceEvent ditambahkan di step berikutnya (circular)
                ('event_bongkar', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='item_bongkar_set', to='devices.deviceevent', verbose_name='Event Pembongkaran')),
                ('event_pasang', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='item_pasang_set', to='devices.deviceevent', verbose_name='Event Pemasangan Kembali')),
            ],
            options={'verbose_name': 'Item Bongkar', 'verbose_name_plural': 'Daftar Item Bongkar', 'ordering': ['-tanggal_bongkar', '-created_at']},
        ),

        # 2. Tambah field baru ke DeviceEvent
        migrations.AddField(
            model_name='deviceevent',
            name='pembongkaran_tipe',
            field=models.CharField(blank=True, choices=[('komponen', 'Komponen'), ('perangkat', 'Perangkat')], max_length=10, verbose_name='Tipe Pembongkaran'),
        ),
        migrations.AddField(
            model_name='deviceevent',
            name='serial_komponen_baru',
            field=models.CharField(blank=True, max_length=100, verbose_name='Serial Number Komponen Baru'),
        ),
        migrations.AddField(
            model_name='deviceevent',
            name='posisi_komponen_baru',
            field=models.CharField(blank=True, max_length=50, verbose_name='Posisi / Slot Komponen Baru'),
        ),
        migrations.AddField(
            model_name='deviceevent',
            name='config_aspek',
            field=models.CharField(blank=True, choices=[('ip_address', 'IP Address / Routing'), ('vlan', 'VLAN / Switching'), ('protokol', 'Protokol Komunikasi'), ('firmware', 'Firmware / Software'), ('ntp', 'NTP / Sinkronisasi Waktu'), ('port', 'Konfigurasi Port / Interface'), ('acl', 'ACL / Access Control'), ('credential', 'Password / Credential'), ('parameter', 'Parameter Operasi'), ('lainnya', 'Lainnya')], max_length=20, verbose_name='Aspek Konfigurasi'),
        ),
        migrations.AddField(
            model_name='deviceevent',
            name='komponen_relokasi_ids',
            field=models.JSONField(blank=True, default=list, verbose_name='ID Komponen yang Direlokasi'),
        ),
        migrations.AddField(
            model_name='deviceevent',
            name='item_bongkar_ref',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='pemasangan_events', to='devices.itembongkar', verbose_name='Item Bongkar yang Dipasang'),
        ),
    ]
