from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('maintenance', '0023_maintenancecorrective_komponen_terkait_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='MaintenanceTeleproteksi',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                # Informasi Umum
                ('suhu_ruangan',         models.FloatField(blank=True, null=True, verbose_name='Suhu Ruangan (°C)')),
                ('kebersihan_perangkat', models.CharField(blank=True, max_length=10, verbose_name='Kebersihan Perangkat',
                                         choices=[('Bersih','Bersih'),('Kotor','Kotor')])),
                ('kebersihan_panel',     models.CharField(blank=True, max_length=10, verbose_name='Kebersihan Panel',
                                         choices=[('Bersih','Bersih'),('Kotor','Kotor')])),
                ('lampu',               models.CharField(blank=True, max_length=3, verbose_name='Lampu',
                                         choices=[('OK','OK'),('NOK','NOK')])),
                # Informasi Perangkat
                ('link',            models.CharField(blank=True, max_length=200, verbose_name='Link (terhubung ke)')),
                ('tipe_tp',         models.CharField(blank=True, max_length=10,  verbose_name='Tipe Teleproteksi',
                                     choices=[('Digital','Digital'),('Analog','Analog')])),
                ('versi_program',   models.CharField(blank=True, max_length=100, verbose_name='Versi Program')),
                ('address_tp',      models.CharField(blank=True, max_length=100, verbose_name='Address TP (Digital)')),
                ('port_comm',       models.CharField(blank=True, max_length=10,  verbose_name='Port Comm TP',
                                     choices=[('E1','E1'),('G64','G64'),('E&M','E&M'),('PLC','PLC')])),
                ('akses_tp',        models.CharField(blank=True, max_length=3,   verbose_name='Akses TP',
                                     choices=[('OK','OK'),('NOK','NOK')])),
                ('remote_akses_tp', models.CharField(blank=True, max_length=3,   verbose_name='Remote Akses TP',
                                     choices=[('OK','OK'),('NOK','NOK')])),
                # Kondisi Peralatan
                ('jumlah_skema', models.PositiveSmallIntegerField(blank=True, null=True, verbose_name='Jumlah Skema')),
                # Skema 1
                ('skema_1_command',       models.CharField(blank=True, max_length=20, verbose_name='Skema 1 Command',
                                           choices=[('','— Pilih —'),('Distance','Distance'),('DEF','DEF'),('DTT','DTT'),('Tidak Terpakai','Tidak Terpakai')])),
                ('skema_1_send_minus',    models.FloatField(blank=True, null=True, verbose_name='Skema 1 Teg Standby Send (-) V')),
                ('skema_1_send_plus',     models.FloatField(blank=True, null=True, verbose_name='Skema 1 Teg Standby Send (+) V')),
                ('skema_1_receive_minus', models.FloatField(blank=True, null=True, verbose_name='Skema 1 Teg Standby Receive (-) V')),
                ('skema_1_receive_plus',  models.FloatField(blank=True, null=True, verbose_name='Skema 1 Teg Standby Receive (+) V')),
                # Skema 2
                ('skema_2_command',       models.CharField(blank=True, max_length=20, verbose_name='Skema 2 Command',
                                           choices=[('','— Pilih —'),('Distance','Distance'),('DEF','DEF'),('DTT','DTT'),('Tidak Terpakai','Tidak Terpakai')])),
                ('skema_2_send_minus',    models.FloatField(blank=True, null=True, verbose_name='Skema 2 Teg Standby Send (-) V')),
                ('skema_2_send_plus',     models.FloatField(blank=True, null=True, verbose_name='Skema 2 Teg Standby Send (+) V')),
                ('skema_2_receive_minus', models.FloatField(blank=True, null=True, verbose_name='Skema 2 Teg Standby Receive (-) V')),
                ('skema_2_receive_plus',  models.FloatField(blank=True, null=True, verbose_name='Skema 2 Teg Standby Receive (+) V')),
                # Skema 3
                ('skema_3_command',       models.CharField(blank=True, max_length=20, verbose_name='Skema 3 Command',
                                           choices=[('','— Pilih —'),('Distance','Distance'),('DEF','DEF'),('DTT','DTT'),('Tidak Terpakai','Tidak Terpakai')])),
                ('skema_3_send_minus',    models.FloatField(blank=True, null=True, verbose_name='Skema 3 Teg Standby Send (-) V')),
                ('skema_3_send_plus',     models.FloatField(blank=True, null=True, verbose_name='Skema 3 Teg Standby Send (+) V')),
                ('skema_3_receive_minus', models.FloatField(blank=True, null=True, verbose_name='Skema 3 Teg Standby Receive (-) V')),
                ('skema_3_receive_plus',  models.FloatField(blank=True, null=True, verbose_name='Skema 3 Teg Standby Receive (+) V')),
                # Skema 4
                ('skema_4_command',       models.CharField(blank=True, max_length=20, verbose_name='Skema 4 Command',
                                           choices=[('','— Pilih —'),('Distance','Distance'),('DEF','DEF'),('DTT','DTT'),('Tidak Terpakai','Tidak Terpakai')])),
                ('skema_4_send_minus',    models.FloatField(blank=True, null=True, verbose_name='Skema 4 Teg Standby Send (-) V')),
                ('skema_4_send_plus',     models.FloatField(blank=True, null=True, verbose_name='Skema 4 Teg Standby Send (+) V')),
                ('skema_4_receive_minus', models.FloatField(blank=True, null=True, verbose_name='Skema 4 Teg Standby Receive (-) V')),
                ('skema_4_receive_plus',  models.FloatField(blank=True, null=True, verbose_name='Skema 4 Teg Standby Receive (+) V')),
                # Pengujian
                ('skema_1_send_result',    models.CharField(blank=True, max_length=3, choices=[('OK','OK'),('NOK','NOK')], verbose_name='Pengujian Send Command 1')),
                ('skema_1_receive_result', models.CharField(blank=True, max_length=3, choices=[('OK','OK'),('NOK','NOK')], verbose_name='Pengujian Receive Command 1')),
                ('skema_2_send_result',    models.CharField(blank=True, max_length=3, choices=[('OK','OK'),('NOK','NOK')], verbose_name='Pengujian Send Command 2')),
                ('skema_2_receive_result', models.CharField(blank=True, max_length=3, choices=[('OK','OK'),('NOK','NOK')], verbose_name='Pengujian Receive Command 2')),
                ('skema_3_send_result',    models.CharField(blank=True, max_length=3, choices=[('OK','OK'),('NOK','NOK')], verbose_name='Pengujian Send Command 3')),
                ('skema_3_receive_result', models.CharField(blank=True, max_length=3, choices=[('OK','OK'),('NOK','NOK')], verbose_name='Pengujian Receive Command 3')),
                ('skema_4_send_result',    models.CharField(blank=True, max_length=3, choices=[('OK','OK'),('NOK','NOK')], verbose_name='Pengujian Send Command 4')),
                ('skema_4_receive_result', models.CharField(blank=True, max_length=3, choices=[('OK','OK'),('NOK','NOK')], verbose_name='Pengujian Receive Command 4')),
                ('time_sync',  models.CharField(blank=True, max_length=3, choices=[('OK','OK'),('NOK','NOK')], verbose_name='Time Sync')),
                ('loop_test',  models.FloatField(blank=True, null=True, verbose_name='Loop Test (ms)')),
                ('catatan',    models.TextField(blank=True, verbose_name='Catatan')),
                ('maintenance', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    to='maintenance.maintenance'
                )),
            ],
            options={'verbose_name': 'Maintenance Teleproteksi'},
        ),
    ]
