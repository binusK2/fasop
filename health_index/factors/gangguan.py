"""
health_index/factors/gangguan.py — Faktor Gangguan Aktif
"""
from .base import BaseFactor


class GangguanAktifFactor(BaseFactor):
    key  = 'gangguan_aktif'
    nama = 'Gangguan Aktif'
    icon = 'bi-lightning-charge'

    def calculate(self, device, bobot_maks):
        from gangguan.models import Gangguan

        gangguan_open = Gangguan.objects.filter(
            peralatan=device, status__in=['open', 'in_progress']
        )
        total = gangguan_open.count()

        raw_deduksi = 0
        for g in gangguan_open:
            raw_deduksi -= {'kritis': 10, 'tinggi': 7, 'sedang': 4}.get(g.tingkat_keparahan, 2)

        # Proporsional terhadap bobot_maks
        if raw_deduksi == 0:
            deduksi = 0
        else:
            deduksi = round(max(raw_deduksi, -15) / -15 * bobot_maks)

        if total == 0:
            status, ket = 'good',    'Tidak ada gangguan aktif'
        elif total == 1:
            status, ket = 'warning', '1 gangguan aktif sedang ditangani'
        else:
            status, ket = 'danger',  f'{total} gangguan aktif belum terselesaikan'

        return self._result(f'{total} gangguan', ket, deduksi, status, bobot_maks)
