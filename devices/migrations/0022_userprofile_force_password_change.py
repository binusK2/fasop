from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('devices', '0021_gruptipekomponen_alter_device_ip_address_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='force_password_change',
            field=models.BooleanField(
                default=True,
                help_text='Jika aktif, user akan diarahkan ke halaman ganti password saat login berikutnya.',
                verbose_name='Wajib Ganti Password',
            ),
        ),
    ]
