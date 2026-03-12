from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('maintenance', '0013_maintenancerectifier'),
    ]

    operations = [
        migrations.RemoveField(model_name='maintenancerectifier', name='bat2_merk'),
        migrations.RemoveField(model_name='maintenancerectifier', name='bat2_tipe'),
        migrations.RemoveField(model_name='maintenancerectifier', name='bat2_kondisi'),
        migrations.RemoveField(model_name='maintenancerectifier', name='bat2_kapasitas'),
        migrations.RemoveField(model_name='maintenancerectifier', name='bat2_jumlah'),
        migrations.RemoveField(model_name='maintenancerectifier', name='bat2_kondisi_kabel'),
        migrations.RemoveField(model_name='maintenancerectifier', name='bat2_kondisi_mur_baut'),
        migrations.RemoveField(model_name='maintenancerectifier', name='bat2_kondisi_sel_rak'),
        migrations.RemoveField(model_name='maintenancerectifier', name='bat2_air_battery'),
        migrations.RemoveField(model_name='maintenancerectifier', name='bat2_v_total'),
        migrations.RemoveField(model_name='maintenancerectifier', name='bat2_v_load'),
        migrations.RemoveField(model_name='maintenancerectifier', name='bat2_cells'),
    ]
