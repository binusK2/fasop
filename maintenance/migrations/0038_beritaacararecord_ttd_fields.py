from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('maintenance', '0037_beritaacararecord_beritaacaraeviden'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='beritaacararecord',
            name='ttd_status',
            field=models.CharField(
                choices=[
                    ('draft', 'Draft'),
                    ('menunggu_engineer', 'Menunggu TTD Engineer'),
                    ('signed_engineer', 'Sudah TTD Engineer'),
                    ('signed_am', 'Selesai'),
                ],
                default='draft',
                max_length=30,
            ),
        ),
        migrations.AddField(
            model_name='beritaacararecord',
            name='ttd_req_to',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='ba_ttd_requests',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name='beritaacararecord',
            name='ttd_engineer',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='ba_signed_engineer',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name='beritaacararecord',
            name='ttd_engineer_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='beritaacararecord',
            name='ttd_am',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='ba_signed_am',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name='beritaacararecord',
            name='ttd_am_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
