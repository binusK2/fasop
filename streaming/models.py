import secrets

from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone


def _gen_token():
    return secrets.token_urlsafe(24)


class LiveSession(models.Model):
    """
    Satu sesi live streaming pemeliharaan lapangan.

    Video utama dipublish oleh `teknisi` dan dibaca semua viewer (Teknisi/AM).
    Talkback audio (komunikasi 2 arah) hanya antara `teknisi` dan `pengawas` —
    dipublish oleh pengawas, dibaca hanya oleh teknisi. Semua akses ke media
    server (MediaMTX) divalidasi lewat token di bawah, dicek via webhook auth
    (lihat streaming.views.mediamtx_auth_webhook) — bukan lewat sesi Django,
    karena request WHIP/WHEP dikirim langsung oleh browser ke MediaMTX.
    """
    STATUS_CHOICES = (
        ('live',  'Live'),
        ('ended', 'Selesai'),
    )

    teknisi      = models.ForeignKey(User, on_delete=models.CASCADE, related_name='live_sessions', verbose_name='Teknisi')
    pengawas     = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='live_sessions_pengawas', verbose_name='Pengawas (AM)')
    judul        = models.CharField(max_length=200, blank=True, verbose_name='Judul / Lokasi Pemeliharaan')

    # Token rahasia untuk otorisasi publish/read di MediaMTX — jangan pernah ditampilkan di UI publik
    stream_key   = models.CharField(max_length=64, unique=True, editable=False, verbose_name='Token Publish Video')
    pengawas_key = models.CharField(max_length=64, blank=True, editable=False, verbose_name='Token Publish Talkback')
    view_token   = models.CharField(max_length=64, unique=True, editable=False, verbose_name='Token Baca Video')

    status       = models.CharField(max_length=10, choices=STATUS_CHOICES, default='live')
    started_at   = models.DateTimeField(auto_now_add=True)
    ended_at     = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-started_at']
        verbose_name = 'Sesi Live Streaming'
        verbose_name_plural = 'Sesi Live Streaming'

    def __str__(self):
        nama = self.teknisi.get_full_name() or self.teknisi.username
        return f'{self.judul or "Live"} — {nama} ({self.get_status_display()})'

    def save(self, *args, **kwargs):
        if not self.stream_key:
            self.stream_key = _gen_token()
        if not self.view_token:
            self.view_token = _gen_token()
        super().save(*args, **kwargs)

    @property
    def is_live(self):
        return self.status == 'live'

    @property
    def video_path(self):
        """Path MediaMTX untuk video utama: publish oleh teknisi, dibaca semua viewer."""
        return f'live-{self.stream_key}'

    @property
    def talkback_path(self):
        """Path MediaMTX untuk audio talkback: publish oleh pengawas, dibaca hanya teknisi."""
        return f'live-{self.stream_key}-talk'

    def assign_pengawas(self, user):
        self.pengawas = user
        self.pengawas_key = _gen_token()
        self.save(update_fields=['pengawas', 'pengawas_key'])

    def end(self):
        self.status = 'ended'
        self.ended_at = timezone.now()
        self.save(update_fields=['status', 'ended_at'])
