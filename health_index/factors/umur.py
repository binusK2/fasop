"""
health_index/factors/umur.py — Faktor Umur Peralatan
"""
from datetime import date as date_type
from .base import BaseFactor


class UmurPeralatanFactor(BaseFactor):
    key  = 'umur_peralatan'
    nama = 'Umur Peralatan'
    icon = 'bi-calendar3'

    def calculate(self, device, bobot_maks):
        if device.tahun_operasi:
            umur = date_type.today().year - device.tahun_operasi
            if umur >= 20:
                deduksi, status, ket = bobot_maks, 'danger',  f'{umur} tahun — sudah melewati usia ekonomis'
            elif umur >= 15:
                deduksi, status, ket = round(bobot_maks * 0.85), 'danger',  f'{umur} tahun — mendekati akhir usia pakai'
            elif umur >= 10:
                deduksi, status, ket = round(bobot_maks * 0.57), 'warning', f'{umur} tahun — perlu perhatian lebih'
            elif umur >= 5:
                deduksi, status, ket = round(bobot_maks * 0.28), 'info',    f'{umur} tahun — masih dalam batas normal'
            else:
                deduksi, status, ket = 0, 'good', f'{umur} tahun — kondisi baru'
            nilai = f'{umur} tahun (sejak {device.tahun_operasi})'
        else:
            umur = None
            deduksi, status, ket = round(bobot_maks * 0.28), 'unknown', 'Tahun operasi belum diisi'
            nilai = 'Tidak diketahui'

        return self._result(nilai, ket, deduksi, status, bobot_maks)
