from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('maintenance', '0014_remove_bat2_fields'),
    ]

    operations = [
        migrations.RemoveField(model_name='maintenancerectifier', name='rect2_merk'),
        migrations.RemoveField(model_name='maintenancerectifier', name='rect2_tipe'),
        migrations.RemoveField(model_name='maintenancerectifier', name='rect2_kondisi'),
        migrations.RemoveField(model_name='maintenancerectifier', name='rect2_kapasitas'),
        migrations.RemoveField(model_name='maintenancerectifier', name='rect2_v_rectifier'),
        migrations.RemoveField(model_name='maintenancerectifier', name='rect2_v_battery'),
        migrations.RemoveField(model_name='maintenancerectifier', name='rect2_teg_pos_ground'),
        migrations.RemoveField(model_name='maintenancerectifier', name='rect2_teg_neg_ground'),
        migrations.RemoveField(model_name='maintenancerectifier', name='rect2_v_dropper'),
        migrations.RemoveField(model_name='maintenancerectifier', name='rect2_a_rectifier'),
        migrations.RemoveField(model_name='maintenancerectifier', name='rect2_a_battery'),
        migrations.RemoveField(model_name='maintenancerectifier', name='rect2_a_load'),
    ]
