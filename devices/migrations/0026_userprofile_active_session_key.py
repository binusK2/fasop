from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('devices', '0025_fiberopticcore'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='active_session_key',
            field=models.CharField(
                blank=True,
                default='',
                help_text='Session key dari sesi login terakhir. Otomatis diperbarui saat login.',
                max_length=40,
                verbose_name='Session Key Aktif',
            ),
        ),
    ]
