from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone
import inspection.models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('devices', '0027_alter_fiberoptic_tipe_kabel_and_more'),
        ('auth', '0012_alter_user_first_name_max_length'),
    ]

    operations = [
        migrations.CreateModel(
            name='Inspection',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('jenis', models.CharField(max_length=30, verbose_name='Jenis Inspeksi',
                          choices=[('catu_daya','Catu Daya'),('defense_scheme','Rele Defense Scheme')])),
                ('tanggal', models.DateTimeField(default=django.utils.timezone.now, verbose_name='Tanggal Inspeksi')),
                ('foto', models.ImageField(blank=True, null=True, upload_to=inspection.models.inspection_photo_upload, verbose_name='Foto Dokumentasi')),
                ('catatan', models.TextField(blank=True, verbose_name='Catatan Umum')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('device', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='inspections', to='devices.device')),
                ('operator', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='inspections', to='auth.user', verbose_name='Operator')),
            ],
            options={'ordering': ['-tanggal'], 'verbose_name': 'Inspeksi Inservice'},
        ),
        migrations.CreateModel(
            name='InspectionCatuDaya',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('kondisi_rectifier', models.CharField(blank=True, max_length=10, verbose_name='Kondisi Rectifier', choices=[('normal','Normal'),('alarm','Alarm')])),
                ('catatan_rectifier', models.CharField(blank=True, max_length=300, verbose_name='Catatan Rectifier')),
                ('kondisi_baterai', models.CharField(blank=True, max_length=10, verbose_name='Kondisi Baterai', choices=[('bersih','Bersih'),('kotor','Kotor')])),
                ('catatan_baterai', models.CharField(blank=True, max_length=300, verbose_name='Catatan Baterai')),
                ('tegangan_input_ac', models.FloatField(blank=True, null=True, verbose_name='Tegangan Input AC (V)')),
                ('arus_input_ac', models.FloatField(blank=True, null=True, verbose_name='Arus Input AC (A)')),
                ('tegangan_load_dc', models.FloatField(blank=True, null=True, verbose_name='Tegangan Load DC (V)')),
                ('arus_load_dc', models.FloatField(blank=True, null=True, verbose_name='Arus Load DC (A)')),
                ('tegangan_baterai_dc', models.FloatField(blank=True, null=True, verbose_name='Tegangan Baterai DC (V)')),
                ('arus_baterai_dc', models.FloatField(blank=True, null=True, verbose_name='Arus Baterai DC (A)')),
                ('kondisi_keseluruhan', models.CharField(blank=True, max_length=10, verbose_name='Kondisi Keseluruhan', choices=[('bersih','Bersih'),('kotor','Kotor')])),
                ('inspection', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='detail_catu_daya', to='inspection.inspection')),
            ],
            options={'verbose_name': 'Detail Inspeksi Catu Daya'},
        ),
        migrations.CreateModel(
            name='InspectionDefenseScheme',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('kondisi_relay', models.CharField(blank=True, max_length=15, verbose_name='Kondisi Relay', choices=[('normal','Normal'),('alarm','Alarm')])),
                ('catatan_relay', models.CharField(blank=True, max_length=300, verbose_name='Catatan Relay')),
                ('indikator_led', models.CharField(blank=True, max_length=15, verbose_name='Indikator LED/Alarm', choices=[('normal','Normal'),('tidak_normal','Tidak Normal')])),
                ('catatan_led', models.CharField(blank=True, max_length=300, verbose_name='Catatan LED/Alarm')),
                ('sumber_dc', models.FloatField(blank=True, null=True, verbose_name='Sumber DC (V)')),
                ('inspection', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='detail_defense_scheme', to='inspection.inspection')),
            ],
            options={'verbose_name': 'Detail Inspeksi Defense Scheme'},
        ),
    ]
