from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # ── ScadaAvSession ─────────────────────────────────────────────────
        migrations.CreateModel(
            name='ScadaAvSession',
            fields=[
                ('id',           models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nama',         models.CharField(max_length=200, verbose_name='Nama Sesi')),
                ('keterangan',   models.TextField(blank=True, verbose_name='Keterangan')),
                ('periode_awal',  models.DateField(verbose_name='Periode Awal')),
                ('periode_akhir', models.DateField(verbose_name='Periode Akhir')),
                ('master',       models.CharField(choices=[('spectrum','Spectrum'),('survalent','Survalent')], default='spectrum', max_length=20, verbose_name='Sumber Data')),
                ('input_type',   models.CharField(choices=[('soe','File SOE (Historical Messages)'),('avrs','File AVRS (RTU Preprocessed)'),('avrcd','File AVRCD (RCD Preprocessed)')], default='soe', max_length=10, verbose_name='Tipe File Input')),
                ('calc_type',    models.CharField(choices=[('rtu','RTU Availability'),('rcd','RCD Success Rate'),('both','RTU + RCD')], default='both', max_length=10, verbose_name='Tipe Kalkulasi')),
                ('status',       models.CharField(choices=[('pending','Menunggu'),('processing','Memproses'),('done','Selesai'),('error','Error')], default='pending', max_length=20)),
                ('error_message',  models.TextField(blank=True)),
                ('durasi_hitung',  models.FloatField(default=0, verbose_name='Durasi Kalkulasi (s)')),
                ('dibuat_pada',    models.DateTimeField(auto_now_add=True)),
                ('dibuat_oleh',    models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='scada_av_sessions', to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ['-dibuat_pada'], 'verbose_name': 'Sesi Kalkulasi SCADA AV', 'verbose_name_plural': 'Sesi Kalkulasi SCADA AV'},
        ),

        # ── ScadaAvFile ────────────────────────────────────────────────────
        migrations.CreateModel(
            name='ScadaAvFile',
            fields=[
                ('id',       models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('file',     models.FileField(upload_to='scada_av/uploads/%Y/%m/')),
                ('filename', models.CharField(max_length=255)),
                ('ukuran',   models.PositiveBigIntegerField(default=0, verbose_name='Ukuran (bytes)')),
                ('diunggah_pada', models.DateTimeField(auto_now_add=True)),
                ('session',  models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='files', to='scada_av.scadaavsession')),
            ],
        ),

        # ── RtuAvResult ────────────────────────────────────────────────────
        migrations.CreateModel(
            name='RtuAvResult',
            fields=[
                ('id',                  models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('rtu',                 models.CharField(max_length=100, verbose_name='RTU ID')),
                ('long_name',           models.CharField(blank=True, max_length=200, verbose_name='Nama Lengkap')),
                ('downtime_occurences', models.IntegerField(default=0, verbose_name='Jumlah Downtime')),
                ('total_downtime_s',    models.FloatField(default=0, verbose_name='Total Downtime (s)')),
                ('rtu_downtime_s',      models.FloatField(default=0, verbose_name='RTU Downtime (s)')),
                ('link_downtime_s',     models.FloatField(default=0, verbose_name='Link Downtime (s)')),
                ('other_downtime_s',    models.FloatField(default=0, verbose_name='Other Downtime (s)')),
                ('unclassified_dt_s',   models.FloatField(default=0, verbose_name='Unclassified Downtime (s)')),
                ('time_range_s',        models.FloatField(default=0, verbose_name='Time Range (s)')),
                ('rtu_availability',    models.FloatField(default=0, verbose_name='RTU Availability')),
                ('link_availability',   models.FloatField(default=0, verbose_name='Link Availability')),
                ('overall',             models.FloatField(default=0, verbose_name='Overall')),
                ('session',             models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='rtu_results', to='scada_av.scadaavsession')),
            ],
            options={'ordering': ['rtu'], 'verbose_name': 'RTU Availability Result'},
        ),

        # ── RcdSummary ─────────────────────────────────────────────────────
        migrations.CreateModel(
            name='RcdSummary',
            fields=[
                ('id',                  models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('total_count',         models.IntegerField(default=0, verbose_name='Total RC')),
                ('total_valid',         models.IntegerField(default=0, verbose_name='Valid RC')),
                ('total_success',       models.IntegerField(default=0, verbose_name='Sukses')),
                ('total_failed',        models.IntegerField(default=0, verbose_name='Gagal')),
                ('total_reps',          models.IntegerField(default=0, verbose_name='Repetisi')),
                ('total_marked_unused', models.IntegerField(default=0, verbose_name='Unused')),
                ('success_ratio',       models.FloatField(default=0, verbose_name='Success Rate')),
                ('success_close_ratio', models.FloatField(default=0, verbose_name='Close Success Rate')),
                ('success_open_ratio',  models.FloatField(default=0, verbose_name='Open Success Rate')),
                ('session',             models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='rcd_summary', to='scada_av.scadaavsession')),
            ],
            options={'verbose_name': 'RCD Summary'},
        ),

        # ── RcdBayResult ───────────────────────────────────────────────────
        migrations.CreateModel(
            name='RcdBayResult',
            fields=[
                ('id',           models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('station',      models.CharField(max_length=100, verbose_name='Gardu Induk (B1)')),
                ('bay_b2',       models.CharField(blank=True, max_length=100, verbose_name='B2')),
                ('bay_b3',       models.CharField(max_length=200, verbose_name='Bay (B3)')),
                ('occurences',   models.IntegerField(default=0, verbose_name='Jumlah RC')),
                ('success',      models.IntegerField(default=0, verbose_name='Sukses')),
                ('failed',       models.IntegerField(default=0, verbose_name='Gagal')),
                ('success_rate', models.FloatField(default=0, verbose_name='Success Rate')),
                ('open_success', models.IntegerField(default=0, verbose_name='Open Sukses')),
                ('open_failed',  models.IntegerField(default=0, verbose_name='Open Gagal')),
                ('close_success',models.IntegerField(default=0, verbose_name='Close Sukses')),
                ('close_failed', models.IntegerField(default=0, verbose_name='Close Gagal')),
                ('contribution', models.FloatField(default=0, verbose_name='Kontribusi')),
                ('reduction',    models.FloatField(default=0, verbose_name='Reduksi')),
                ('tagging',      models.CharField(blank=True, max_length=10, verbose_name='Tagging')),
                ('session',      models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='rcd_bay_results', to='scada_av.scadaavsession')),
            ],
            options={'ordering': ['-reduction', '-failed'], 'verbose_name': 'RCD Bay Result'},
        ),
    ]
