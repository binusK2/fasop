from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='AuditLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('action', models.CharField(
                    choices=[
                        ('create', 'Tambah'),
                        ('update', 'Edit'),
                        ('delete', 'Hapus'),
                        ('approve', 'Approval'),
                        ('sign', 'Tanda Tangan'),
                        ('mutasi', 'Mutasi Stok'),
                        ('status', 'Ubah Status'),
                        ('other', 'Lainnya'),
                    ],
                    max_length=20,
                    verbose_name='Aksi',
                )),
                ('app_label', models.CharField(max_length=50, verbose_name='Modul')),
                ('model_name', models.CharField(max_length=100, verbose_name='Objek')),
                ('object_id', models.PositiveIntegerField(blank=True, null=True, verbose_name='ID')),
                ('object_repr', models.CharField(max_length=255, verbose_name='Deskripsi Objek')),
                ('detail', models.TextField(blank=True, verbose_name='Detail')),
                ('ip_address', models.GenericIPAddressField(blank=True, null=True, verbose_name='IP')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Waktu')),
                ('user', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='audit_logs',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='Pengguna',
                )),
            ],
            options={
                'verbose_name': 'Audit Log',
                'verbose_name_plural': 'Audit Log',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='auditlog',
            index=models.Index(fields=['-created_at'], name='auditlog_au_created_idx'),
        ),
        migrations.AddIndex(
            model_name='auditlog',
            index=models.Index(fields=['user'], name='auditlog_au_user_idx'),
        ),
        migrations.AddIndex(
            model_name='auditlog',
            index=models.Index(fields=['action'], name='auditlog_au_action_idx'),
        ),
        migrations.AddIndex(
            model_name='auditlog',
            index=models.Index(fields=['app_label'], name='auditlog_au_app_idx'),
        ),
    ]
