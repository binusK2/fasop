from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('devices', '0010_device_created_by'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='display_name',
            field=models.CharField(
                blank=True,
                default='',
                help_text='Nama lengkap yang akan muncul di PDF (opsional). Jika kosong, pakai nama akun.',
                max_length=150,
                verbose_name='Nama Tampilan / Alias',
            ),
        ),
    ]
