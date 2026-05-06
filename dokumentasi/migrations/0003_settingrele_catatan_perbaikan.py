from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('dokumentasi', '0002_setting_gambar_detail_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='settingrele',
            name='catatan_perbaikan',
            field=models.TextField(
                blank=True,
                verbose_name='Catatan Perbaikan',
                help_text='Diisi checker saat mengembalikan dokumen untuk diperbaiki',
            ),
        ),
    ]
