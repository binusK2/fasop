"""
Export logsheet ke Excel dengan mengisi TEMPLATE asli (format identik).

Template = workbook LOGSHEET_MKS milik operator (VBA dibuang), disimpan di
logsheet/xlsx_template/. Untuk tanggal tertentu, nilai per titik diisi ke 48
kolom waktu pada sheet & baris sesuai LogsheetTitik, menggantikan formula latch
dengan angka statis. Hasilnya sama persis dengan logsheet Excel lama.
"""
import os
from collections import defaultdict

TEMPLATE_PATH = os.path.join(os.path.dirname(__file__), 'xlsx_template',
                             'LOGSHEET_MKS_template.xlsx')

JUMLAH_SLOT = 48


def load_template():
    import openpyxl
    return openpyxl.load_workbook(TEMPLATE_PATH, data_only=False, keep_vba=False)


def build_workbook(tanggal):
    """
    Kembalikan openpyxl Workbook template yang sudah diisi nilai untuk `tanggal`.
    Hanya sheet yang punya SHEET_SLOT_COL0 & titik ber-baris yang diisi.
    """
    from .models import LogsheetTitik, LogsheetNilai

    wb = load_template()
    titik_qs = (LogsheetTitik.objects
                .filter(aktif=True, baris__isnull=False)
                .exclude(sheet='')
                .exclude(baris=0))
    titik_by_id = {t.id: t for t in titik_qs}
    if not titik_by_id:
        return wb

    # 1) Bersihkan SEMUA formula latch (referensi DASHBOARD) di sheet terkelola
    #    — di semua kolom, agar slot tanpa data tampil kosong (bukan nilai basi)
    #    dan menangani sheet berblok ganda (TRAFO: blok MW & MVAR). Formula lain
    #    (subtotal/label) dibiarkan.
    for sheet in {t.sheet for t in titik_by_id.values()}:
        ws = wb[sheet]
        for row in ws.iter_rows():
            for cell in row:
                v = cell.value
                if isinstance(v, str) and v.startswith('=') and 'DASHBOARD' in v:
                    cell.value = None

    # 2) Isi nilai yang tersedia untuk tanggal ini (kolom slot-0 per-titik)
    nilai_qs = (LogsheetNilai.objects
                .filter(titik_id__in=titik_by_id.keys(), tanggal=tanggal,
                        nilai__isnull=False)
                .values_list('titik_id', 'slot', 'nilai'))
    for titik_id, slot, nilai in nilai_qs:
        if not (0 <= slot < JUMLAH_SLOT):
            continue
        t = titik_by_id[titik_id]
        wb[t.sheet].cell(row=t.baris, column=t.kol0 + slot).value = round(nilai, 2)
    return wb


def workbook_to_response(wb, filename):
    """Serialisasi Workbook -> HttpResponse unduhan .xlsx."""
    import io
    from django.http import HttpResponse
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    resp = HttpResponse(
        buf.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    resp['Content-Disposition'] = f'attachment; filename="{filename}"'
    return resp
