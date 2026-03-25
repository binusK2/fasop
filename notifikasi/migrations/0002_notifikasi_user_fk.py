from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('auth', '0012_alter_user_first_name_max_length'),
        ('notifikasi', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='notifikasi',
            name='user',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='notifikasi',
                to='auth.user',
                verbose_name='Ditujukan ke',
            ),
        ),
        migrations.AlterField(
            model_name='notifikasi',
            name='tipe',
            field=models.CharField(max_length=30, choices=[
                ('hi_rendah','Health Index Rendah'),
                ('hi_turun','HI Turun Drastis'),
                ('maintenance_overdue','Maintenance Overdue'),
                ('gangguan_lama','Gangguan Terlalu Lama'),
                ('maintenance_ttd','Maintenance Perlu TTD'),
                ('gangguan_selesai','Gangguan Selesai — Perlu Review'),
                ('gangguan_baru','Gangguan Baru Dibuat'),
                ('corrective_selesai','Corrective Selesai'),
            ]),
        ),
        migrations.AlterField(
            model_name='notifikasi',
            name='level',
            field=models.CharField(max_length=10, default='warning', choices=[
                ('danger','Danger'),('warning','Warning'),('info','Info'),('success','Success'),
            ]),
        ),
    ]
