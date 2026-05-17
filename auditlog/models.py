from django.db import models
from django.contrib.auth.models import User


class AuditLog(models.Model):
    CREATE  = 'create'
    UPDATE  = 'update'
    DELETE  = 'delete'
    APPROVE = 'approve'
    SIGN    = 'sign'
    MUTASI  = 'mutasi'
    STATUS  = 'status'
    OTHER   = 'other'

    ACTION_CHOICES = [
        (CREATE,  'Tambah'),
        (UPDATE,  'Edit'),
        (DELETE,  'Hapus'),
        (APPROVE, 'Approval'),
        (SIGN,    'Tanda Tangan'),
        (MUTASI,  'Mutasi Stok'),
        (STATUS,  'Ubah Status'),
        (OTHER,   'Lainnya'),
    ]

    ACTION_COLORS = {
        CREATE:  'success',
        UPDATE:  'primary',
        DELETE:  'danger',
        APPROVE: 'info',
        SIGN:    'info',
        MUTASI:  'warning',
        STATUS:  'secondary',
        OTHER:   'secondary',
    }

    user        = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='audit_logs', verbose_name='Pengguna',
    )
    action      = models.CharField(max_length=20, choices=ACTION_CHOICES, verbose_name='Aksi')
    app_label   = models.CharField(max_length=50, verbose_name='Modul')
    model_name  = models.CharField(max_length=100, verbose_name='Objek')
    object_id   = models.PositiveIntegerField(null=True, blank=True, verbose_name='ID')
    object_repr = models.CharField(max_length=255, verbose_name='Deskripsi Objek')
    detail      = models.TextField(blank=True, verbose_name='Detail')
    ip_address  = models.GenericIPAddressField(null=True, blank=True, verbose_name='IP')
    created_at  = models.DateTimeField(auto_now_add=True, verbose_name='Waktu')

    class Meta:
        verbose_name        = 'Audit Log'
        verbose_name_plural = 'Audit Log'
        ordering            = ['-created_at']
        indexes             = [
            models.Index(fields=['-created_at']),
            models.Index(fields=['user']),
            models.Index(fields=['action']),
            models.Index(fields=['app_label']),
        ]

    def __str__(self):
        return f'{self.created_at:%Y-%m-%d %H:%M} | {self.user} | {self.get_action_display()} | {self.object_repr}'

    @property
    def action_color(self):
        return self.ACTION_COLORS.get(self.action, 'secondary')
