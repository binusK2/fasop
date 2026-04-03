from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('inspection', '0004_relay_fields'),
        ('auth', '0012_alter_user_first_name_max_length'),
    ]

    operations = [
        migrations.AddField(
            model_name='inspection',
            name='is_flagged',
            field=models.BooleanField(default=False, verbose_name='Diflag'),
        ),
        migrations.AddField(
            model_name='inspection',
            name='flag_catatan',
            field=models.TextField(blank=True, verbose_name='Catatan Flag'),
        ),
        migrations.AddField(
            model_name='inspection',
            name='flagged_by',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='flagged_inspections',
                to='auth.user',
                verbose_name='Diflag oleh',
            ),
        ),
        migrations.AddField(
            model_name='inspection',
            name='flagged_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Waktu Flag'),
        ),
    ]
