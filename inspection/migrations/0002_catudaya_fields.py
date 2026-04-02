from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('inspection', '0001_initial'),
    ]

    operations = [
        # Rectifier mode
        migrations.AddField(
            model_name='inspectioncatudaya',
            name='mode_recti',
            field=models.CharField(blank=True, max_length=15, verbose_name='Mode Rectifier',
                                   choices=[('float','Float'),('boost','Boost'),('equalizing','Equalizing')]),
        ),
        # Alarm fields
        migrations.AddField(
            model_name='inspectioncatudaya',
            name='alarm_ground_fault',
            field=models.CharField(blank=True, max_length=10, verbose_name='Alarm Ground Fault',
                                   choices=[('ada','Ada'),('tidak_ada','Tidak Ada')]),
        ),
        migrations.AddField(
            model_name='inspectioncatudaya',
            name='alarm_min_ac_fault',
            field=models.CharField(blank=True, max_length=10, verbose_name='Alarm Min AC Fault',
                                   choices=[('ada','Ada'),('tidak_ada','Tidak Ada')]),
        ),
        migrations.AddField(
            model_name='inspectioncatudaya',
            name='alarm_recti_fault',
            field=models.CharField(blank=True, max_length=10, verbose_name='Alarm Recti Fault',
                                   choices=[('ada','Ada'),('tidak_ada','Tidak Ada')]),
        ),
        # Kebersihan ruangan rectifier
        migrations.AddField(
            model_name='inspectioncatudaya',
            name='kebersihan_ruangan',
            field=models.CharField(blank=True, max_length=10, verbose_name='Kebersihan Ruangan',
                                   choices=[('bersih','Bersih'),('kotor','Kotor')]),
        ),
        # Bank fields
        migrations.AddField(
            model_name='inspectioncatudaya',
            name='level_air_bank',
            field=models.CharField(blank=True, max_length=15, verbose_name='Level Air Bank',
                                   choices=[('normal','Normal'),('bawah_level','Di Bawah Level'),('atas_level','Di Atas Level')]),
        ),
        migrations.AddField(
            model_name='inspectioncatudaya',
            name='kebersihan_ruangan_bank',
            field=models.CharField(blank=True, max_length=10, verbose_name='Kebersihan Ruangan Bank',
                                   choices=[('bersih','Bersih'),('kotor','Kotor')]),
        ),
        migrations.AddField(
            model_name='inspectioncatudaya',
            name='kebersihan_bank',
            field=models.CharField(blank=True, max_length=10, verbose_name='Kebersihan Bank',
                                   choices=[('bersih','Bersih'),('kotor','Kotor')]),
        ),
        migrations.AddField(
            model_name='inspectioncatudaya',
            name='exhaust_fan',
            field=models.CharField(blank=True, max_length=10, verbose_name='Exhaust Fan',
                                   choices=[('nyala','Nyala'),('mati','Mati')]),
        ),
    ]
