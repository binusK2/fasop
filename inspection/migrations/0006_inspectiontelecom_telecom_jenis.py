from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('inspection', '0005_inspection_flag'),
    ]

    operations = [
        # Tambah 'telecom' ke JENIS_CHOICES di Inspection
        migrations.AlterField(
            model_name='inspection',
            name='jenis',
            field=models.CharField(
                max_length=30,
                choices=[
                    ('catu_daya',      'Catu Daya'),
                    ('defense_scheme', 'Rele Defense Scheme'),
                    ('master_trip',    'Master Trip'),
                    ('ufls',           'UFLS'),
                    ('telecom',        'Pengujian Telekomunikasi'),
                ],
                verbose_name='Jenis Inspeksi',
            ),
        ),
        # Buat model InspectionTelecom
        migrations.CreateModel(
            name='InspectionTelecom',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('hasil_komunikasi', models.CharField(
                    blank=True, max_length=15,
                    choices=[('normal', 'Normal'), ('tidak_normal', 'Tidak Normal')],
                    verbose_name='Hasil Pengujian Komunikasi',
                )),
                ('kualitas_suara', models.CharField(
                    blank=True, max_length=10,
                    choices=[('baik', 'Baik'), ('cukup', 'Cukup'), ('buruk', 'Buruk')],
                    verbose_name='Kualitas Suara',
                )),
                ('catatan_pengujian', models.TextField(blank=True, verbose_name='Catatan Pengujian')),
                ('inspection', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='detail_telecom',
                    to='inspection.inspection',
                )),
            ],
            options={'verbose_name': 'Detail Pengujian Telekomunikasi'},
        ),
    ]
