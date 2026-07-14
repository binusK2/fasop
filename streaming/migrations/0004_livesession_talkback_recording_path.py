from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("streaming", "0003_liveviewerheartbeat"),
    ]

    operations = [
        migrations.AddField(
            model_name="livesession",
            name="talkback_recording_path",
            field=models.CharField(
                blank=True, editable=False, max_length=500, verbose_name="Path Rekaman Audio Pengawas"
            ),
        ),
    ]
