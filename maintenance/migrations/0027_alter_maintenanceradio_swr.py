from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('maintenance', '0026_alter_maintenancegenset_tangki_bbm_sebelum_and_more'),
    ]

    operations = [
        # Bersihkan nilai lama yang tidak bisa dikonversi ke float
        migrations.RunSQL(
            "UPDATE maintenance_maintenanceradio SET swr = NULL WHERE swr IS NOT NULL AND swr != '';",
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.AlterField(
            model_name='maintenanceradio',
            name='swr',
            field=models.FloatField(blank=True, null=True, verbose_name='SWR'),
        ),
    ]
