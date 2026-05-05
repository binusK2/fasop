from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('maintenance', '0038_beritaacararecord_ttd_fields'),
    ]

    operations = [
        # Skema 1
        migrations.AddField(model_name='maintenanceteleproteksi', name='skema_1_send_teg',
            field=models.CharField(blank=True, choices=[('48','48 V'),('110','110 V'),('220','220 V'),('standby','Standby')], max_length=10, verbose_name='Skema 1 Teg Send')),
        migrations.AddField(model_name='maintenanceteleproteksi', name='skema_1_send_pol',
            field=models.CharField(blank=True, choices=[('negatif','Negatif'),('positif','Positif')], max_length=10, verbose_name='Skema 1 Polaritas Send')),
        migrations.AddField(model_name='maintenanceteleproteksi', name='skema_1_receive_teg',
            field=models.CharField(blank=True, choices=[('48','48 V'),('110','110 V'),('220','220 V'),('standby','Standby')], max_length=10, verbose_name='Skema 1 Teg Receive')),
        migrations.AddField(model_name='maintenanceteleproteksi', name='skema_1_receive_pol',
            field=models.CharField(blank=True, choices=[('negatif','Negatif'),('positif','Positif')], max_length=10, verbose_name='Skema 1 Polaritas Receive')),
        # Skema 2
        migrations.AddField(model_name='maintenanceteleproteksi', name='skema_2_send_teg',
            field=models.CharField(blank=True, choices=[('48','48 V'),('110','110 V'),('220','220 V'),('standby','Standby')], max_length=10, verbose_name='Skema 2 Teg Send')),
        migrations.AddField(model_name='maintenanceteleproteksi', name='skema_2_send_pol',
            field=models.CharField(blank=True, choices=[('negatif','Negatif'),('positif','Positif')], max_length=10, verbose_name='Skema 2 Polaritas Send')),
        migrations.AddField(model_name='maintenanceteleproteksi', name='skema_2_receive_teg',
            field=models.CharField(blank=True, choices=[('48','48 V'),('110','110 V'),('220','220 V'),('standby','Standby')], max_length=10, verbose_name='Skema 2 Teg Receive')),
        migrations.AddField(model_name='maintenanceteleproteksi', name='skema_2_receive_pol',
            field=models.CharField(blank=True, choices=[('negatif','Negatif'),('positif','Positif')], max_length=10, verbose_name='Skema 2 Polaritas Receive')),
        # Skema 3
        migrations.AddField(model_name='maintenanceteleproteksi', name='skema_3_send_teg',
            field=models.CharField(blank=True, choices=[('48','48 V'),('110','110 V'),('220','220 V'),('standby','Standby')], max_length=10, verbose_name='Skema 3 Teg Send')),
        migrations.AddField(model_name='maintenanceteleproteksi', name='skema_3_send_pol',
            field=models.CharField(blank=True, choices=[('negatif','Negatif'),('positif','Positif')], max_length=10, verbose_name='Skema 3 Polaritas Send')),
        migrations.AddField(model_name='maintenanceteleproteksi', name='skema_3_receive_teg',
            field=models.CharField(blank=True, choices=[('48','48 V'),('110','110 V'),('220','220 V'),('standby','Standby')], max_length=10, verbose_name='Skema 3 Teg Receive')),
        migrations.AddField(model_name='maintenanceteleproteksi', name='skema_3_receive_pol',
            field=models.CharField(blank=True, choices=[('negatif','Negatif'),('positif','Positif')], max_length=10, verbose_name='Skema 3 Polaritas Receive')),
        # Skema 4
        migrations.AddField(model_name='maintenanceteleproteksi', name='skema_4_send_teg',
            field=models.CharField(blank=True, choices=[('48','48 V'),('110','110 V'),('220','220 V'),('standby','Standby')], max_length=10, verbose_name='Skema 4 Teg Send')),
        migrations.AddField(model_name='maintenanceteleproteksi', name='skema_4_send_pol',
            field=models.CharField(blank=True, choices=[('negatif','Negatif'),('positif','Positif')], max_length=10, verbose_name='Skema 4 Polaritas Send')),
        migrations.AddField(model_name='maintenanceteleproteksi', name='skema_4_receive_teg',
            field=models.CharField(blank=True, choices=[('48','48 V'),('110','110 V'),('220','220 V'),('standby','Standby')], max_length=10, verbose_name='Skema 4 Teg Receive')),
        migrations.AddField(model_name='maintenanceteleproteksi', name='skema_4_receive_pol',
            field=models.CharField(blank=True, choices=[('negatif','Negatif'),('positif','Positif')], max_length=10, verbose_name='Skema 4 Polaritas Receive')),
    ]
