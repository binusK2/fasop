# Ditulis manual: file BA upload hanya PDF/Word, dan isinya diperiksa.

import maintenance.models
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('maintenance', '0059_maintenance_deleted_by_maintenance_is_deleted_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='beritaacararecord',
            name='file_upload',
            field=models.FileField(blank=True, help_text='Dokumen BA yang sudah jadi (hasil upload langsung, tanpa generate PDF)', null=True, upload_to=maintenance.models.ba_file_upload, validators=[maintenance.models.validate_ba_file_ekstensi, maintenance.models.validate_ba_file_size, maintenance.models.validate_ba_file_isi], verbose_name='File BA (Upload)'),
        ),
    ]
