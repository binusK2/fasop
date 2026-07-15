from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('opsis', '0007_snaptrafo'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='snaptrafo',
            name='q',
        ),
    ]
