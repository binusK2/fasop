from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('auth', '0012_alter_user_first_name_max_length'),
    ]

    operations = [
        migrations.CreateModel(
            name='JadwalKunjungan',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('lokasi', models.CharField(max_length=150, verbose_name='Lokasi / Site')),
                ('bulan_rencana', models.PositiveSmallIntegerField(verbose_name='Bulan Rencana')),
                ('tahun_rencana', models.PositiveSmallIntegerField(verbose_name='Tahun Rencana')),
                ('status', models.CharField(
                    max_length=20,
                    choices=[('planned','Terjadwal'),('in_progress','Sedang Berjalan'),('done','Selesai')],
                    default='planned'
                )),
                ('catatan', models.TextField(blank=True, verbose_name='Catatan')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_by', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='jadwal_dibuat',
                    to='auth.user',
                    verbose_name='Dibuat oleh'
                )),
            ],
            options={
                'verbose_name': 'Jadwal Kunjungan',
                'verbose_name_plural': 'Jadwal Kunjungan',
                'ordering': ['tahun_rencana', 'bulan_rencana', 'lokasi'],
                'unique_together': {('lokasi', 'bulan_rencana', 'tahun_rencana')},
            },
        ),
    ]
