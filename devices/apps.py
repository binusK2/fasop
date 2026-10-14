from django.apps import AppConfig


class DevicesConfig(AppConfig):
    name = 'devices'

    def ready(self):
        import devices.signals  # noqa: F401
        matikan_ghostscript()


def matikan_ghostscript():
    """
    Pillow merender EPS/PostScript dengan memanggil Ghostscript (`gs`) — sebuah
    interpreter. FASOP membuka gambar unggahan pengguna di tiga tempat (validasi
    ImageField, thumbnail foto lapangan, gambar di PDF WeasyPrint), dan Pillow
    memilih parser dari ISI berkas, bukan ekstensinya: EPS yang dinamai
    `foto.jpg` tetap dibuka sebagai EPS. Kalau Ghostscript terpasang di server,
    satu unggahan cukup untuk menjalankan PostScript buatan penyerang
    (GHSA-r543-q48m-4c9j).

    FASOP tidak pernah butuh EPS, jadi Ghostscript dimatikan untuk seluruh
    proses — termasuk cron — bukan cuma di jalur WeasyPrint yang sudah ditambal
    upstream. Pillow lalu menolak EPS dengan OSError, yang sudah ditangani semua
    pemanggilnya sebagai "bukan gambar valid".
    """
    from PIL import EpsImagePlugin
    EpsImagePlugin.gs_binary = False
