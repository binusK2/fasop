from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('devices', '0049_komponenrusak_branch'),
    ]

    operations = [
        migrations.AlterField(
            model_name='userprofile',
            name='role',
            field=models.CharField(
                default='technician',
                max_length=30,
                verbose_name='Peran',
                choices=[
                    ('viewer',          'Viewer (Hanya Lihat)'),
                    ('operator',        'Operator'),
                    ('dispatcher',      'Dispatcher — Pengujian Telekomunikasi'),
                    ('technician',      'Teknisi / Engineer'),
                    ('asisten_manager', 'Asisten Manager Operasi'),
                    ('opsis',           'Opsis — Monitoring Pembangkit'),
                ],
            ),
        ),
    ]
