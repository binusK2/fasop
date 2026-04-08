from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import devices.models


class Migration(migrations.Migration):

    dependencies = [
        ('devices', '0030_userloginlog'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='DeviceEviden',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('foto', models.ImageField(upload_to=devices.models.device_eviden_upload)),
                ('keterangan', models.CharField(blank=True, default='', max_length=200)),
                ('uploaded_at', models.DateTimeField(auto_now_add=True)),
                ('device', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='eviden_list', to='devices.device')),
                ('uploaded_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['uploaded_at'],
            },
        ),
    ]
