from django.db import migrations


class Migration(migrations.Migration):
    """
    Tambah role 'operator' ke UserProfile.ROLE_CHOICES.
    Tidak ada perubahan skema DB — hanya update choices list.
    """

    dependencies = [
        ('devices', '0027_alter_fiberoptic_tipe_kabel_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='userprofile',
            name='role',
            field=__import__('django.db.models', fromlist=['CharField']).CharField(
                choices=[
                    ('viewer',          'Viewer (Hanya Lihat)'),
                    ('operator',        'Operator'),
                    ('technician',      'Teknisi / Engineer'),
                    ('asisten_manager', 'Asisten Manager Operasi'),
                ],
                default='technician',
                max_length=30,
                verbose_name='Peran',
            ),
        ),
    ]
