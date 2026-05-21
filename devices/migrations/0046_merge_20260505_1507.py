from django.db import migrations


class Migration(migrations.Migration):
    """
    Merge migration: reconciles the 0044 branch (local otdr_b_catatan alters)
    with the 0045 branch (komponen_baru fields).
    """

    dependencies = [
        ('devices', '0044_alter_fiberopticcore_otdr_b_catatan_and_more'),
        ('devices', '0045_add_komponen_baru_fields_and_komponen_rusak'),
    ]

    operations = [
    ]
