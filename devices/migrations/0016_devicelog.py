from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('auth', '0012_alter_user_first_name_max_length'),
        ('devices', '0015_device_tahun_operasi'),
    ]

    operations = [
        migrations.CreateModel(
            name='DeviceLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('aksi', models.CharField(
                    max_length=10,
                    choices=[('create','Dibuat'),('edit','Diedit'),('delete','Dihapus')]
                )),
                ('perubahan', models.JSONField(default=list)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('device', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='logs',
                    to='devices.device',
                )),
                ('user', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='device_logs',
                    to='auth.user',
                )),
            ],
            options={
                'verbose_name': 'Log Perubahan Device',
                'verbose_name_plural': 'Log Perubahan Device',
                'ordering': ['-created_at'],
            },
        ),
    ]
