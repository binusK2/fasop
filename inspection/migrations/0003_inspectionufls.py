from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('inspection', '0002_catudaya_fields'),
    ]

    operations = [
        migrations.CreateModel(
            name='InspectionUFLS',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True,
                                           serialize=False, verbose_name='ID')),
                ('kondisi_relay', models.CharField(blank=True, max_length=15,
                    verbose_name='Kondisi Relay',
                    choices=[('normal','Normal'),('alarm','Alarm')])),
                ('catatan_relay', models.CharField(blank=True, max_length=300,
                    verbose_name='Catatan Relay')),
                ('indikator_led', models.CharField(blank=True, max_length=15,
                    verbose_name='Indikator LED/Alarm',
                    choices=[('normal','Normal'),('tidak_normal','Tidak Normal')])),
                ('catatan_led', models.CharField(blank=True, max_length=300,
                    verbose_name='Catatan LED/Alarm')),
                ('sumber_dc', models.FloatField(blank=True, null=True,
                    verbose_name='Sumber DC (V)')),
                ('inspection', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='detail_ufls',
                    to='inspection.inspection')),
            ],
            options={'verbose_name': 'Detail Inspeksi UFLS'},
        ),
    ]
