from django.db import migrations, models
import maintenance.models


class Migration(migrations.Migration):

    dependencies = [
        ('maintenance', '0049_maintenancemasterstation'),
    ]

    operations = [
        migrations.AddField(
            model_name='beritaacararecord',
            name='file_upload',
            field=models.FileField(blank=True, help_text='Dokumen BA yang sudah jadi (hasil upload langsung, tanpa generate PDF)', null=True, upload_to=maintenance.models.ba_file_upload, verbose_name='File BA (Upload)'),
        ),
        migrations.AlterField(
            model_name='beritaacararecord',
            name='jenis',
            field=models.CharField(choices=[('pemasangan', 'Pemasangan'), ('pembongkaran', 'Pembongkaran'), ('penggantian', 'Penggantian'), ('gangguan', 'Gangguan'), ('penormalan', 'Penormalan'), ('lainnya', 'Lainnya')], max_length=20),
        ),
    ]
