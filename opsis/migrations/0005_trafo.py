from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('opsis', '0004_snapfreq'),
    ]

    operations = [
        migrations.CreateModel(
            name='Trafo',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('site', models.CharField(max_length=100, verbose_name='Site (GI)')),
                ('bay', models.CharField(max_length=50, verbose_name='Bay (Tag MSSQL)')),
                ('urutan', models.PositiveIntegerField(default=0, verbose_name='Urutan Tampil')),
                ('aktif', models.BooleanField(default=True, verbose_name='Aktif')),
            ],
            options={
                'verbose_name': 'Trafo',
                'verbose_name_plural': 'Trafo',
                'ordering': ['urutan', 'site', 'bay'],
                'unique_together': {('site', 'bay')},
            },
        ),
    ]
