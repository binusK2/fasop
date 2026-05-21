from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('inspection', '0007_pengujiantelecom'),
    ]

    operations = [
        migrations.AddField(
            model_name='pengujiantelecom',
            name='jenis',
            field=models.CharField(
                choices=[('radio', 'Radio'), ('voip', 'VoIP'), ('all', 'Radio & VoIP')],
                default='all',
                max_length=10,
                verbose_name='Jenis Pengujian',
            ),
        ),
    ]
