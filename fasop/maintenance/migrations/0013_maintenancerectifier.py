from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('maintenance', '0012_maintenancemux'),
    ]

    operations = [
        migrations.CreateModel(
            name='MaintenanceRectifier',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                # Lingkungan
                ('suhu_ruangan',     models.FloatField(blank=True, null=True)),
                ('exhaust_fan',      models.CharField(blank=True, max_length=20, choices=[('Terpasang','Terpasang'),('Tidak Terpasang','Tidak Terpasang'),('Rusak','Rusak')])),
                ('kebersihan',       models.CharField(blank=True, max_length=10, choices=[('Bersih','Bersih'),('Kotor','Kotor')])),
                ('lampu_penerangan', models.CharField(blank=True, max_length=15, choices=[('Menyala','Menyala'),('Tidak Menyala','Tidak Menyala'),('Redup','Redup')])),
                # Rectifier 1
                ('rect1_merk',models.CharField(blank=True,max_length=100)),('rect1_tipe',models.CharField(blank=True,max_length=100)),
                ('rect1_kondisi',models.CharField(blank=True,max_length=3,choices=[('OK','OK'),('NOK','NOK')])),
                ('rect1_kapasitas',models.CharField(blank=True,max_length=50)),
                ('rect1_v_rectifier',models.FloatField(blank=True,null=True)),('rect1_v_battery',models.FloatField(blank=True,null=True)),
                ('rect1_teg_pos_ground',models.FloatField(blank=True,null=True)),('rect1_teg_neg_ground',models.FloatField(blank=True,null=True)),
                ('rect1_v_dropper',models.FloatField(blank=True,null=True)),
                ('rect1_a_rectifier',models.FloatField(blank=True,null=True)),('rect1_a_battery',models.FloatField(blank=True,null=True)),
                ('rect1_a_load',models.FloatField(blank=True,null=True)),
                # Rectifier 2
                ('rect2_merk',models.CharField(blank=True,max_length=100)),('rect2_tipe',models.CharField(blank=True,max_length=100)),
                ('rect2_kondisi',models.CharField(blank=True,max_length=3,choices=[('OK','OK'),('NOK','NOK')])),
                ('rect2_kapasitas',models.CharField(blank=True,max_length=50)),
                ('rect2_v_rectifier',models.FloatField(blank=True,null=True)),('rect2_v_battery',models.FloatField(blank=True,null=True)),
                ('rect2_teg_pos_ground',models.FloatField(blank=True,null=True)),('rect2_teg_neg_ground',models.FloatField(blank=True,null=True)),
                ('rect2_v_dropper',models.FloatField(blank=True,null=True)),
                ('rect2_a_rectifier',models.FloatField(blank=True,null=True)),('rect2_a_battery',models.FloatField(blank=True,null=True)),
                ('rect2_a_load',models.FloatField(blank=True,null=True)),
                # Battery Bank 1
                ('bat1_merk',models.CharField(blank=True,max_length=100)),('bat1_tipe',models.CharField(blank=True,max_length=100)),
                ('bat1_kondisi',models.CharField(blank=True,max_length=3,choices=[('OK','OK'),('NOK','NOK')])),
                ('bat1_kapasitas',models.CharField(blank=True,max_length=50)),('bat1_jumlah',models.IntegerField(blank=True,null=True)),
                ('bat1_kondisi_kabel',models.CharField(blank=True,max_length=3,choices=[('OK','OK'),('NOK','NOK')])),
                ('bat1_kondisi_mur_baut',models.CharField(blank=True,max_length=3,choices=[('OK','OK'),('NOK','NOK')])),
                ('bat1_kondisi_sel_rak',models.CharField(blank=True,max_length=3,choices=[('OK','OK'),('NOK','NOK')])),
                ('bat1_air_battery',models.FloatField(blank=True,null=True)),
                ('bat1_v_total',models.FloatField(blank=True,null=True)),('bat1_v_load',models.FloatField(blank=True,null=True)),
                ('bat1_cells',models.JSONField(blank=True,default=list)),
                # Battery Bank 2
                ('bat2_merk',models.CharField(blank=True,max_length=100)),('bat2_tipe',models.CharField(blank=True,max_length=100)),
                ('bat2_kondisi',models.CharField(blank=True,max_length=3,choices=[('OK','OK'),('NOK','NOK')])),
                ('bat2_kapasitas',models.CharField(blank=True,max_length=50)),('bat2_jumlah',models.IntegerField(blank=True,null=True)),
                ('bat2_kondisi_kabel',models.CharField(blank=True,max_length=3,choices=[('OK','OK'),('NOK','NOK')])),
                ('bat2_kondisi_mur_baut',models.CharField(blank=True,max_length=3,choices=[('OK','OK'),('NOK','NOK')])),
                ('bat2_kondisi_sel_rak',models.CharField(blank=True,max_length=3,choices=[('OK','OK'),('NOK','NOK')])),
                ('bat2_air_battery',models.FloatField(blank=True,null=True)),
                ('bat2_v_total',models.FloatField(blank=True,null=True)),('bat2_v_load',models.FloatField(blank=True,null=True)),
                ('bat2_cells',models.JSONField(blank=True,default=list)),
                # Catatan
                ('catatan',models.TextField(blank=True)),
                ('maintenance',models.OneToOneField(on_delete=django.db.models.deletion.CASCADE,to='maintenance.maintenance')),
            ],
            options={'verbose_name': 'Maintenance Rectifier & Battery'},
        ),
    ]
