from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('devices', '0047_ip_unique_per_lokasi'),
    ]

    operations = [
        migrations.CreateModel(
            name='Branch',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nama', models.CharField(max_length=100, unique=True, verbose_name='Nama Branch')),
                ('kode', models.CharField(blank=True, max_length=20, verbose_name='Kode')),
                ('keterangan', models.TextField(blank=True, verbose_name='Keterangan')),
            ],
            options={
                'verbose_name': 'Branch',
                'verbose_name_plural': 'Branch',
                'ordering': ['nama'],
            },
        ),
        migrations.AddField(
            model_name='sitelocation',
            name='branch',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='lokasi_set',
                to='devices.branch',
                verbose_name='Branch',
            ),
        ),
    ]
