from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('health_index', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='KonfigurasiHI',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('faktor_key', models.CharField(max_length=50, unique=True, verbose_name='Kode Faktor')),
                ('nama', models.CharField(max_length=100, verbose_name='Nama Faktor')),
                ('icon', models.CharField(default='bi-circle', max_length=50, verbose_name='Icon')),
                ('bobot_maks', models.IntegerField(
                    verbose_name='Bobot Maks (negatif)',
                    help_text='Nilai negatif, contoh: -25'
                )),
                ('aktif', models.BooleanField(default=True, verbose_name='Aktif')),
                ('urutan', models.PositiveSmallIntegerField(default=0, verbose_name='Urutan Tampil')),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Konfigurasi Health Index',
                'verbose_name_plural': 'Konfigurasi Health Index',
                'ordering': ['urutan', 'faktor_key'],
            },
        ),
    ]
