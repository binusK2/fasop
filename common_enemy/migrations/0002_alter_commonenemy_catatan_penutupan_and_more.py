import common_enemy.models
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('common_enemy', '0001_initial'),
        ('devices', '0046_merge_20260505_1507'),
    ]

    operations = [
        migrations.AlterField(
            model_name='commonenemy',
            name='catatan_penutupan',
            field=models.TextField(
                blank=True,
                verbose_name='Catatan Penutupan',
                help_text='Diisi saat issue dinyatakan selesai / closed',
            ),
        ),
        migrations.AlterField(
            model_name='commonenemy',
            name='deskripsi_masalah',
            field=models.TextField(
                verbose_name='Deskripsi Masalah',
                help_text='Uraian lengkap masalah yang dilaporkan',
            ),
        ),
    ]
