from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('dokumentasi', '0003_settingrele_catatan_perbaikan'),
    ]

    operations = [
        migrations.AlterField(
            model_name='settingrele',
            name='status',
            field=models.CharField(
                max_length=25,
                choices=[
                    ('draft',           'Draft'),
                    ('on_check',        'On Check'),
                    ('perlu_perbaikan', 'Perlu Perbaikan'),
                    ('uptodate',        'Up to Date'),
                ],
                default='draft',
                verbose_name='Status',
            ),
        ),
    ]
