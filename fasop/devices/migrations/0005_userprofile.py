from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('devices', '0004_remove_icon_image_icon_sid1_icon_sid2_icon_bandwidth_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='UserProfile',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('role', models.CharField(
                    max_length=30,
                    choices=[
                        ('technician', 'Teknisi / Pelaksana'),
                        ('asisten_manager', 'Asisten Manager Operasi'),
                    ],
                    default='technician',
                    verbose_name='Peran',
                )),
                ('signature', models.ImageField(
                    upload_to='signatures/',
                    blank=True, null=True,
                    verbose_name='Tanda Tangan',
                )),
                ('user', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='profile',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={'verbose_name': 'Profil Pengguna'},
        ),
    ]
