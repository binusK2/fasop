from django.db import migrations


class Migration(migrations.Migration):
    """
    Merge migration: converges the otdr-branch (0046_merge_20260505_1507)
    with the main devices chain (0050_userprofile_dispatcher_role) into a
    single leaf node, so future makemigrations won't need --merge.
    """

    dependencies = [
        ('devices', '0046_merge_20260505_1507'),
        ('devices', '0050_userprofile_dispatcher_role'),
    ]

    operations = [
    ]
