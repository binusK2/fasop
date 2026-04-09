from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('maintenance', '0026_alter_maintenancegenset_tangki_bbm_sebelum_and_more'),
    ]

    operations = [
        # Konversi tipe sekaligus dalam satu ALTER TABLE:
        # - Nilai numerik (misal "1.2") → float
        # - Nilai non-numerik ("<1.5", ">1.5", "") → NULL
        # - DROP NOT NULL agar FloatField(null=True) valid
        migrations.RunSQL(
            sql="""
                ALTER TABLE maintenance_maintenanceradio
                ALTER COLUMN swr TYPE double precision
                USING CASE
                    WHEN swr ~ '^[0-9]+(\\.[0-9]+)?$' THEN swr::double precision
                    ELSE NULL
                END;

                ALTER TABLE maintenance_maintenanceradio
                ALTER COLUMN swr DROP NOT NULL;
            """,
            reverse_sql=migrations.RunSQL.noop,
        ),
        # Sinkronkan state Django (tanpa menyentuh DB lagi)
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AlterField(
                    model_name='maintenanceradio',
                    name='swr',
                    field=models.FloatField(blank=True, null=True, verbose_name='SWR'),
                ),
            ],
            database_operations=[],
        ),
    ]
