from django import forms
from django.contrib import admin, messages
from django.utils.html import format_html

from . import ezviz
from .models import EzvizToken, KameraEzviz, LiveSession, PengaturanEzviz


@admin.register(LiveSession)
class LiveSessionAdmin(admin.ModelAdmin):
    list_display = ('judul', 'sumber', 'kamera', 'teknisi', 'pengawas', 'status', 'started_at', 'ended_at')
    list_filter = ('status', 'sumber')
    search_fields = ('judul', 'teknisi__username', 'pengawas__username', 'kamera__nama')
    readonly_fields = ('stream_key', 'pengawas_key', 'view_token', 'started_at', 'ended_at')
    autocomplete_fields = ('kamera',)
    date_hierarchy = 'started_at'


@admin.register(KameraEzviz)
class KameraEzvizAdmin(admin.ModelAdmin):
    list_display = ('nama', 'lokasi', 'serial', 'channel', 'hd', 'terenkripsi', 'aktif', 'status_cloud', 'terakhir_sinkron')
    list_filter = ('aktif', 'hd', 'status_cloud', 'lokasi')
    list_editable = ('aktif', 'hd')
    search_fields = ('nama', 'serial', 'lokasi', 'keterangan')
    readonly_fields = ('status_cloud', 'terakhir_sinkron', 'ezopen_url', 'created_at', 'updated_at')
    actions = ('aksi_sinkron_dari_ezviz', 'aksi_aktifkan', 'aksi_nonaktifkan')
    fieldsets = (
        (None, {'fields': ('nama', 'lokasi', 'keterangan', 'aktif')}),
        ('Alamat di Cloud Ezviz', {
            'fields': ('serial', 'channel', 'hd', 'kode_verifikasi', 'ezopen_url'),
            'description': (
                'Serial + channel inilah yang menentukan video mana yang diputar. '
                'Nama & lokasi murni label untuk manusia dan tidak pernah ditimpa '
                'oleh sinkronisasi dari cloud.'
            ),
        }),
        ('Sinkronisasi', {'fields': ('status_cloud', 'terakhir_sinkron', 'created_at', 'updated_at')}),
    )

    @admin.display(boolean=True, description='Kode verifikasi terisi')
    def terenkripsi(self, obj):
        return bool(obj.kode_verifikasi)

    @admin.display(description='Alamat ezopen')
    def ezopen_url(self, obj):
        return obj.ezopen_url if obj.pk else '—'

    @admin.action(description='Sinkronkan daftar kamera dari akun Ezviz')
    def aksi_sinkron_dari_ezviz(self, request, queryset):
        """
        Sengaja mengabaikan `queryset`: yang ditarik adalah SELURUH daftar
        kamera akun, bukan baris yang dicentang — mustahil menyinkronkan
        kamera yang belum ada barisnya kalau dibatasi pilihan.
        """
        if not ezviz.terkonfigurasi():
            self.message_user(request, 'EZVIZ_APP_KEY/EZVIZ_APP_SECRET belum diisi di .env.', messages.ERROR)
            return
        try:
            hasil = ezviz.sinkron_kamera()
        except ezviz.EzvizError as e:
            self.message_user(request, f'Sinkronisasi gagal: {e}', messages.ERROR)
            return
        self.message_user(
            request,
            f"{hasil['total']} kamera di cloud — {hasil['dibuat']} baru, "
            f"{hasil['diperbarui']} diperbarui, {hasil['hilang']} tidak lagi ada di cloud.",
            messages.SUCCESS,
        )

    @admin.action(description='Aktifkan kamera terpilih')
    def aksi_aktifkan(self, request, queryset):
        n = queryset.update(aktif=True)
        self.message_user(request, f'{n} kamera diaktifkan.', messages.SUCCESS)

    @admin.action(description='Nonaktifkan kamera terpilih')
    def aksi_nonaktifkan(self, request, queryset):
        n = queryset.update(aktif=False)
        self.message_user(request, f'{n} kamera dinonaktifkan.', messages.SUCCESS)


@admin.register(EzvizToken)
class EzvizTokenAdmin(admin.ModelAdmin):
    """
    Baris tunggal (pk=1) yang diisi otomatis. Ditampilkan supaya pertanyaan
    "kenapa kamera Ezviz tidak muncul" bisa dijawab dari admin — kalau
    expire_at sudah lewat atau kosong, masalahnya di kredensial, bukan di
    kameranya. Tidak bisa ditambah/diedit manual: token hanya sah kalau
    datang dari Ezviz.
    """
    list_display = ('__str__', 'expire_at', 'masih_berlaku', 'updated_at')
    readonly_fields = ('token', 'expire_at', 'updated_at')

    @admin.display(boolean=True, description='Masih berlaku')
    def masih_berlaku(self, obj):
        return obj.masih_berlaku

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


class PengaturanEzvizForm(forms.ModelForm):
    """appSecret disembunyikan di layar, tapi TETAP terkirim saat form dibuka
    (render_value) — kalau tidak, menyimpan perubahan kecil di kolom lain akan
    diam-diam mengosongkan secret-nya."""

    class Meta:
        model = PengaturanEzviz
        fields = '__all__'
        widgets = {'app_secret': forms.PasswordInput(render_value=True)}


@admin.register(PengaturanEzviz)
class PengaturanEzvizAdmin(admin.ModelAdmin):
    """
    Satu baris pengaturan. Superuser saja (seperti seluruh site admin) —
    appSecret adalah kredensial seluruh akun Ezviz, bukan sesuatu yang boleh
    disunting pemakai biasa.
    """
    form = PengaturanEzvizForm
    readonly_fields = ('status_token', 'updated_at')
    fieldsets = (
        ('Kredensial', {
            'fields': ('app_key', 'app_secret'),
            'description': (
                'Dari console Ezviz Open Platform. Kolom yang dikosongkan jatuh ke '
                'nilai di .env, jadi pemasangan yang sudah memakai .env tidak berubah. '
                '<br><strong>appKey &amp; appSecret tidak kedaluwarsa</strong> — yang '
                'berumur ~7 hari adalah accessToken, dan itu diperbarui sendiri.'
            ),
        }),
        ('Endpoint', {
            'fields': ('api_base', 'ezopen_host'),
            'description': (
                'Biarkan kosong kalau tidak yakin. Setelah menyimpan, jalankan '
                '<code>python manage.py cek_ezviz</code> untuk memastikan kredensial '
                'dan alamat kameranya diterima Ezviz.'
            ),
        }),
        ('Status', {'fields': ('status_token', 'updated_at')}),
    )

    @admin.display(description='Token & region')
    def status_token(self, obj):
        baris = EzvizToken.objects.filter(pk=1).first()
        if not baris or not baris.token:
            return 'Belum ada token — akan diambil otomatis saat kamera pertama kali diputar.'
        return format_html(
            'Berlaku sampai <strong>{}</strong> ({}) · region: {}',
            baris.expire_at.strftime('%d/%m/%Y %H:%M') if baris.expire_at else '—',
            'masih berlaku' if baris.masih_berlaku else 'sudah basi, akan diperbarui',
            baris.area_domain or 'mengikuti Host API',
        )

    def has_add_permission(self, request):
        # Baris tunggal: dibuat otomatis saat pertama kali dibuka.
        return not PengaturanEzviz.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False

    def changelist_view(self, request, extra_context=None):
        PengaturanEzviz.objects.get_or_create(pk=1)
        return super().changelist_view(request, extra_context)

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if any(f in form.changed_data for f in ('app_key', 'app_secret', 'api_base')):
            self.message_user(
                request,
                'Kredensial berubah — token lama dibuang, token baru diambil otomatis '
                'saat kamera berikutnya diputar. Jalankan "manage.py cek_ezviz" untuk memastikan.',
                messages.WARNING,
            )
