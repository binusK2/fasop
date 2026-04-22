from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='Pembangkit',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nama', models.CharField(max_length=100, verbose_name='Nama Pembangkit')),
                ('kode', models.CharField(max_length=20, unique=True, verbose_name='Kode')),
                ('warna', models.CharField(default='#3b82f6', max_length=7, verbose_name='Warna Chart')),
                ('urutan', models.PositiveIntegerField(default=0, verbose_name='Urutan Tampil')),
                ('aktif', models.BooleanField(default=True, verbose_name='Aktif')),
                ('tag_frekuensi', models.CharField(blank=True, max_length=200, verbose_name='Tag Frekuensi (MSSQL)')),
                ('tag_mw', models.CharField(blank=True, max_length=200, verbose_name='Tag Daya MW (MSSQL)')),
                ('tag_mvar', models.CharField(blank=True, max_length=200, verbose_name='Tag Daya MVAR (MSSQL)')),
            ],
            options={
                'verbose_name': 'Pembangkit',
                'verbose_name_plural': 'Pembangkit',
                'ordering': ['urutan', 'nama'],
            },
        ),
    ]
