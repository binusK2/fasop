from django.db import migrations


class Migration(migrations.Migration):
    """
    Merge migration: gabungkan cabang 0039 (teleproteksi skema fields)
    dengan main chain yang dilanjutkan dari 0040 ke 0044.
    """

    dependencies = [
        ('maintenance', '0039_teleproteksi_teg_standby_polaritas'),
        ('maintenance', '0044_maintenancertugeneric'),
    ]

    operations = [
    ]
