from django.db import migrations, models
import django.db.models.deletion


KEBERSIHAN = [('bersih','Bersih'),('kotor','Kotor')]
LAMPU      = [('nyala','Nyala'),('mati','Mati')]
KONDISI    = [('normal','Normal'),('faulty','Faulty')]
SELEKTOR   = [('on_aktif','ON / Aktif'),('off_nonaktif','OFF / Nonaktif')]
KABEL      = [('terpasang','Terpasang'),('terlepas','Terlepas'),('tidak_tersedia','Tidak Tersedia')]


class Migration(migrations.Migration):

    dependencies = [
        ('inspection', '0003_inspectionufls'),
    ]

    operations = [

        # 1. Buat tabel InspectionMasterTrip (belum ada migration sebelumnya)
        migrations.CreateModel(
            name='InspectionMasterTrip',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True,
                                           serialize=False, verbose_name='ID')),
                ('suhu_ruangan',      models.FloatField(blank=True, null=True, verbose_name='Suhu Ruangan (C)')),
                ('kebersihan_panel',  models.CharField(blank=True, max_length=10, choices=KEBERSIHAN, verbose_name='Kebersihan Panel')),
                ('lampu_panel',       models.CharField(blank=True, max_length=10, choices=LAMPU, verbose_name='Lampu Panel')),
                ('kondisi_relay',     models.CharField(blank=True, max_length=15, choices=KONDISI, verbose_name='Kondisi Rele')),
                ('relay_healthy',     models.CharField(blank=True, max_length=15, choices=KONDISI, verbose_name='Relay Healthy')),
                ('indikator_led',     models.CharField(blank=True, max_length=15, choices=KONDISI, verbose_name='Indikasi LED')),
                ('catatan_relay',     models.CharField(blank=True, max_length=300, verbose_name='Catatan Relay')),
                ('posisi_selektor',   models.CharField(blank=True, max_length=15, choices=SELEKTOR, verbose_name='Posisi Selektor Target')),
                ('kondisi_kabel_lan', models.CharField(blank=True, max_length=20, choices=KABEL, verbose_name='Kondisi Kabel LAN')),
                ('sumber_dc',         models.FloatField(blank=True, null=True, verbose_name='Sumber DC (V)')),
                ('inspection', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='detail_master_trip',
                    to='inspection.inspection',
                )),
            ],
            options={'verbose_name': 'Detail Inspeksi Master Trip'},
        ),

        # 2. Update InspectionDefenseScheme
        migrations.RemoveField(model_name='inspectiondefensescheme', name='catatan_led'),
        migrations.AlterField(
            model_name='inspectiondefensescheme', name='kondisi_relay',
            field=models.CharField(blank=True, max_length=15, choices=KONDISI, verbose_name='Kondisi Rele'),
        ),
        migrations.AlterField(
            model_name='inspectiondefensescheme', name='indikator_led',
            field=models.CharField(blank=True, max_length=15, choices=KONDISI, verbose_name='Indikasi LED'),
        ),
        migrations.AddField(model_name='inspectiondefensescheme', name='suhu_ruangan',
            field=models.FloatField(blank=True, null=True, verbose_name='Suhu Ruangan (C)')),
        migrations.AddField(model_name='inspectiondefensescheme', name='kebersihan_panel',
            field=models.CharField(blank=True, max_length=10, choices=KEBERSIHAN, verbose_name='Kebersihan Panel')),
        migrations.AddField(model_name='inspectiondefensescheme', name='lampu_panel',
            field=models.CharField(blank=True, max_length=10, choices=LAMPU, verbose_name='Lampu Panel')),
        migrations.AddField(model_name='inspectiondefensescheme', name='relay_healthy',
            field=models.CharField(blank=True, max_length=15, choices=KONDISI, verbose_name='Relay Healthy')),
        migrations.AddField(model_name='inspectiondefensescheme', name='posisi_selektor',
            field=models.CharField(blank=True, max_length=15, choices=SELEKTOR, verbose_name='Posisi Selektor Target')),
        migrations.AddField(model_name='inspectiondefensescheme', name='kondisi_kabel_lan',
            field=models.CharField(blank=True, max_length=20, choices=KABEL, verbose_name='Kondisi Kabel LAN')),

        # 3. Update InspectionUFLS
        migrations.RemoveField(model_name='inspectionufls', name='catatan_led'),
        migrations.AlterField(
            model_name='inspectionufls', name='kondisi_relay',
            field=models.CharField(blank=True, max_length=15, choices=KONDISI, verbose_name='Kondisi Rele'),
        ),
        migrations.AlterField(
            model_name='inspectionufls', name='indikator_led',
            field=models.CharField(blank=True, max_length=15, choices=KONDISI, verbose_name='Indikasi LED'),
        ),
        migrations.AddField(model_name='inspectionufls', name='suhu_ruangan',
            field=models.FloatField(blank=True, null=True, verbose_name='Suhu Ruangan (C)')),
        migrations.AddField(model_name='inspectionufls', name='kebersihan_panel',
            field=models.CharField(blank=True, max_length=10, choices=KEBERSIHAN, verbose_name='Kebersihan Panel')),
        migrations.AddField(model_name='inspectionufls', name='lampu_panel',
            field=models.CharField(blank=True, max_length=10, choices=LAMPU, verbose_name='Lampu Panel')),
        migrations.AddField(model_name='inspectionufls', name='relay_healthy',
            field=models.CharField(blank=True, max_length=15, choices=KONDISI, verbose_name='Relay Healthy')),
        migrations.AddField(model_name='inspectionufls', name='posisi_selektor',
            field=models.CharField(blank=True, max_length=15, choices=SELEKTOR, verbose_name='Posisi Selektor Target')),
        migrations.AddField(model_name='inspectionufls', name='kondisi_kabel_lan',
            field=models.CharField(blank=True, max_length=20, choices=KABEL, verbose_name='Kondisi Kabel LAN')),
    ]
