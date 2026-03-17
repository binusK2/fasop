from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('devices', '0012_device_foto2'),
    ]

    operations = [
        migrations.CreateModel(
            name='SiteLocation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nama', models.CharField(
                    max_length=150,
                    unique=True,
                    verbose_name='Nama Site',
                    help_text='Harus sama persis dengan nilai lokasi pada data Device'
                )),
                ('latitude', models.FloatField(null=True, blank=True, verbose_name='Latitude')),
                ('longitude', models.FloatField(null=True, blank=True, verbose_name='Longitude')),
                ('keterangan', models.TextField(blank=True, null=True, verbose_name='Keterangan')),
            ],
            options={
                'verbose_name': 'Lokasi Site',
                'verbose_name_plural': 'Lokasi Site',
                'ordering': ['nama'],
            },
        ),
    ]
