from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('maintenance', '0016_maintenancerectifier_catatan'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # 1. Tambah field technicians (M2M)
        migrations.AddField(
            model_name='maintenance',
            name='technicians',
            field=models.ManyToManyField(
                to=settings.AUTH_USER_MODEL,
                blank=True,
                related_name='maintenance_technician_set',
                verbose_name='Pelaksana',
            ),
        ),
        # 2. Salin data FK lama ke M2M  → dilakukan lewat RunPython
        migrations.RunPython(
            code=lambda apps, schema_editor: [
                m.technicians.add(m.technician)
                for m in apps.get_model('maintenance', 'Maintenance').objects.filter(technician__isnull=False)
            ],
            reverse_code=migrations.RunPython.noop,
        ),
        # 3. Hapus FK lama
        migrations.RemoveField(
            model_name='maintenance',
            name='technician',
        ),
        # 4. Tambah signed_by + signed_at
        migrations.AddField(
            model_name='maintenance',
            name='signed_by',
            field=models.ForeignKey(
                to=settings.AUTH_USER_MODEL,
                on_delete=django.db.models.deletion.SET_NULL,
                null=True, blank=True,
                related_name='signed_maintenances',
                verbose_name='Ditandatangani oleh',
            ),
        ),
        migrations.AddField(
            model_name='maintenance',
            name='signed_at',
            field=models.DateTimeField(null=True, blank=True, verbose_name='Waktu TTD'),
        ),
    ]
