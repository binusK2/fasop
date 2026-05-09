from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('devices', '0046_devicelink'),
    ]

    operations = [
        # 1. Hapus constraint unique global pada ip_address
        migrations.AlterField(
            model_name='device',
            name='ip_address',
            field=models.GenericIPAddressField(blank=True, null=True),
        ),
        # 2. Tambah constraint unik per (ip_address, lokasi) — hanya bila ip tidak null
        migrations.AddConstraint(
            model_name='device',
            constraint=models.UniqueConstraint(
                condition=models.Q(ip_address__isnull=False),
                fields=['ip_address', 'lokasi'],
                name='unique_ip_per_lokasi',
            ),
        ),
    ]
