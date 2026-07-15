from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('opsis', '0006_snapfreqarea'),
    ]

    operations = [
        migrations.CreateModel(
            name='SnapTrafo',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('waktu', models.DateTimeField()),
                ('p', models.FloatField(null=True)),
                ('q', models.FloatField(null=True)),
                ('dicatat_pada', models.DateTimeField(auto_now_add=True)),
                ('trafo', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='snaps', to='opsis.trafo')),
            ],
            options={
                'verbose_name': 'Snapshot Trafo',
                'verbose_name_plural': 'Snapshots Trafo',
                'ordering': ['-waktu'],
                'unique_together': {('trafo', 'waktu')},
            },
        ),
        migrations.AddIndex(
            model_name='snaptrafo',
            index=models.Index(fields=['trafo', '-waktu'], name='opsis_snapt_trafo_i_53ce05_idx'),
        ),
    ]
