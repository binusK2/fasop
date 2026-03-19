from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('gangguan', '0004_tindaklanjut_optional'),
    ]

    operations = [
        migrations.AddField(
            model_name='gangguan',
            name='public_token',
            field=models.CharField(
                blank=True, max_length=40, null=True, unique=True,
                verbose_name='Token Publik',
                help_text='Token unik untuk akses halaman status publik',
            ),
        ),
    ]
