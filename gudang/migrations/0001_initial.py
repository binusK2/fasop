from django.db import migrations, models
import django.db.models.deletion
import gudang.models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('auth', '0012_alter_user_first_name_max_length'),
        ('gangguan', '0010_gangguan_fiber_optic'),
        ('maintenance', '0023_maintenancecorrective_komponen_terkait_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='AlatUji',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nama', models.CharField(max_length=150, verbose_name='Nama Alat')),
                ('kategori', models.CharField(help_text='Contoh: OTDR, Power Meter, Multimeter, Laptop Lapangan', max_length=100, verbose_name='Kategori')),
                ('merk', models.CharField(blank=True, max_length=100, verbose_name='Merk / Brand')),
                ('model', models.CharField(blank=True, max_length=100, verbose_name='Model / Type')),
                ('nomor_seri', models.CharField(blank=True, max_length=100, verbose_name='Nomor Seri')),
                ('kondisi', models.CharField(choices=[('baik', 'Baik'), ('kalibrasi', 'Perlu Kalibrasi'), ('rusak', 'Rusak'), ('perbaikan', 'Dalam Perbaikan')], default='baik', max_length=20, verbose_name='Kondisi')),
                ('lokasi_penyimpanan', models.CharField(help_text='Contoh: Lemari A Ruang Teknik, Gudang Lt.1', max_length=150, verbose_name='Lokasi Penyimpanan')),
                ('tanggal_kalibrasi', models.DateField(blank=True, null=True, verbose_name='Tanggal Kalibrasi Terakhir')),
                ('jadwal_kalibrasi_berikut', models.DateField(blank=True, null=True, verbose_name='Jadwal Kalibrasi Berikutnya')),
                ('keterangan', models.TextField(blank=True, verbose_name='Keterangan')),
                ('foto', models.ImageField(blank=True, null=True, upload_to=gudang.models.alat_foto_upload, verbose_name='Foto Alat')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('is_deleted', models.BooleanField(default=False)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='alat_dibuat', to='auth.user', verbose_name='Ditambahkan oleh')),
            ],
            options={
                'verbose_name': 'Alat Uji',
                'verbose_name_plural': 'Alat Uji',
                'ordering': ['kategori', 'nama'],
            },
        ),
        migrations.CreateModel(
            name='Sparepart',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nama', models.CharField(max_length=150, verbose_name='Nama Spare Part')),
                ('kategori', models.CharField(help_text='Contoh: SFP, Kabel, Baterai, Power Supply', max_length=100, verbose_name='Kategori')),
                ('merk', models.CharField(blank=True, max_length=100, verbose_name='Merk / Brand')),
                ('part_number', models.CharField(blank=True, max_length=100, verbose_name='Part Number')),
                ('satuan', models.CharField(choices=[('pcs', 'pcs'), ('unit', 'unit'), ('meter', 'meter'), ('roll', 'roll'), ('set', 'set'), ('box', 'box')], default='pcs', max_length=10, verbose_name='Satuan')),
                ('lokasi_penyimpanan', models.CharField(max_length=150, verbose_name='Lokasi di Gudang')),
                ('stok_minimum', models.PositiveIntegerField(default=0, help_text='Alert jika stok di bawah nilai ini', verbose_name='Stok Minimum')),
                ('keterangan', models.TextField(blank=True, verbose_name='Keterangan')),
                ('foto', models.ImageField(blank=True, null=True, upload_to=gudang.models.sparepart_foto_upload, verbose_name='Foto')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('is_deleted', models.BooleanField(default=False)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='sparepart_dibuat', to='auth.user', verbose_name='Ditambahkan oleh')),
            ],
            options={
                'verbose_name': 'Spare Part',
                'verbose_name_plural': 'Spare Part',
                'ordering': ['kategori', 'nama'],
            },
        ),
        migrations.CreateModel(
            name='MutasiSparepart',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('tipe', models.CharField(choices=[('masuk', 'Masuk'), ('keluar', 'Keluar')], max_length=10, verbose_name='Tipe Mutasi')),
                ('jumlah', models.PositiveIntegerField(verbose_name='Jumlah')),
                ('keperluan', models.CharField(max_length=255, verbose_name='Keperluan / Keterangan')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('sparepart', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='mutasi', to='gudang.sparepart', verbose_name='Spare Part')),
                ('terkait_gangguan', models.ForeignKey(blank=True, help_text='Opsional — hubungkan ke tiket gangguan', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='mutasi_sparepart', to='gangguan.gangguan', verbose_name='Terkait Gangguan')),
                ('terkait_maintenance', models.ForeignKey(blank=True, help_text='Opsional — hubungkan ke jadwal maintenance', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='mutasi_sparepart', to='maintenance.maintenance', verbose_name='Terkait Maintenance')),
                ('dilakukan_oleh', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='mutasi_sparepart', to='auth.user', verbose_name='Dicatat oleh')),
            ],
            options={
                'verbose_name': 'Mutasi Spare Part',
                'verbose_name_plural': 'Mutasi Spare Part',
                'ordering': ['-created_at'],
            },
        ),
    ]
