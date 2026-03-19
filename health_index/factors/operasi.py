"""
health_index/factors/operasi.py — Faktor Status Operasi
"""
from .base import BaseFactor


class StatusOperasiFactor(BaseFactor):
    key  = 'status_operasi'
    nama = 'Status Operasi'
    icon = 'bi-activity'

    def calculate(self, device, bobot_maks):
        if device.status_operasi == 'tidak_operasi':
            return self._result(
                device.get_status_operasi_display(),
                'Peralatan sedang tidak beroperasi',
                bobot_maks, 'danger', bobot_maks
            )
        return self._result(
            device.get_status_operasi_display(),
            'Peralatan beroperasi normal',
            0, 'good', bobot_maks
        )
