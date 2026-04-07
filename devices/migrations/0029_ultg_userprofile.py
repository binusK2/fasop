from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('devices', '0028_userprofile_role_operator'),
    ]

    operations = [
        # Buat tabel ULTG
        migrations.CreateModel(
            name='ULTG',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True,
                                           serialize=False, verbose_name='ID')),
                ('nama', models.CharField(max_length=100, unique=True, verbose_name='Nama ULTG')),
                ('keterangan', models.TextField(blank=True, verbose_name='Keterangan')),
                ('lokasi', models.ManyToManyField(
                    blank=True,
                    to='devices.sitelocation',
                    verbose_name='Lokasi / GI yang dibawahi',
                )),
            ],
            options={
                'verbose_name': 'ULTG',
                'verbose_name_plural': 'ULTG',
                'ordering': ['nama'],
            },
        ),
        # Tambah FK ultg ke UserProfile
        migrations.AddField(
            model_name='userprofile',
            name='ultg',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='operators',
                to='devices.ultg',
                verbose_name='ULTG',
            ),
        ),
    ]
