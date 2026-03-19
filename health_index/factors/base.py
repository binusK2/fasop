"""
health_index/factors/base.py

Base class untuk semua faktor HI.
Setiap faktor harus implement method calculate().
"""


class BaseFactor:
    """
    Base class untuk kalkulasi satu faktor HI.

    Subclass wajib implement:
        - key:   str  — identifier unik (misal: 'umur_peralatan')
        - nama:  str  — nama tampilan
        - icon:  str  — bootstrap icon class
        - calculate(device, bobot_maks) -> dict
    """
    key   = ''
    nama  = ''
    icon  = 'bi-circle'
    # Jenis device yang didukung. None = semua jenis.
    # Isi dengan list nama jenis: ['Router', 'Switch'] dst.
    jenis_support = None

    def is_applicable(self, device):
        """Cek apakah faktor ini relevan untuk device ini."""
        if self.jenis_support is None:
            return True
        if device.jenis is None:
            return False
        return device.jenis.name in self.jenis_support

    def calculate(self, device, bobot_maks):
        """
        Hitung deduksi untuk faktor ini.

        Returns:
            dict dengan keys:
                faktor      str  — nama faktor
                icon        str  — bi icon class
                nilai       str  — nilai aktual yang diukur
                keterangan  str  — penjelasan singkat
                deduksi     int  — pengurangan skor (0 atau negatif)
                maks        int  — bobot_maks dari konfigurasi
                status      str  — 'good' | 'info' | 'warning' | 'danger' | 'unknown'
        """
        raise NotImplementedError

    def _result(self, nilai, keterangan, deduksi, status, bobot_maks):
        """Helper untuk membuat dict hasil kalkulasi."""
        return {
            'faktor':     self.nama,
            'icon':       self.icon,
            'nilai':      nilai,
            'keterangan': keterangan,
            'deduksi':    max(deduksi, bobot_maks),   # tidak boleh melebihi bobot_maks
            'maks':       bobot_maks,
            'status':     status,
        }
