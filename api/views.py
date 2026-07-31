import json
import secrets
import copy
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.db import IntegrityError

from devices.models import Device, DeviceType
from devices.device_audit import log_create, log_edit
from .auth import require_api_key


def _parse_json_body(request):
    try:
        data = json.loads(request.body)
        return data, None
    except (json.JSONDecodeError, ValueError):
        return None, JsonResponse(
            {'status': 'error', 'message': 'Body bukan JSON yang valid.'},
            status=400
        )


def _resolve_fields(data):
    ip_address    = data.get('ip_address',    '').strip() or None
    serial_number = data.get('serial_number', '').strip() or None

    status_operasi = data.get('status_operasi', 'operasi').strip().lower()
    if status_operasi not in ('operasi', 'tidak_operasi'):
        status_operasi = 'operasi'

    tahun_operasi = data.get('tahun_operasi', None)
    if tahun_operasi is not None:
        try:
            tahun_operasi = int(tahun_operasi)
        except (ValueError, TypeError):
            tahun_operasi = None

    return {
        'nama':             data.get('nama', '').strip(),
        'merk':             data.get('merk', '').strip(),
        'type':             data.get('type', '').strip() or None,
        'serial_number':    serial_number,
        'firmware_version': data.get('firmware_version', '').strip() or None,
        'ip_address':       ip_address,
        'lokasi':           data.get('lokasi', '').strip(),
        'status_operasi':   status_operasi,
        'keterangan':       data.get('keterangan', '').strip() or None,
        'tahun_operasi':    tahun_operasi,
    }


@csrf_exempt
@require_api_key
@require_http_methods(["POST", "GET"])
def devices_endpoint(request):
    if request.method == 'GET':
        return _list_devices(request)
    return _upsert_device(request)


def _upsert_device(request):
    data, err = _parse_json_body(request)
    if err:
        return err

    required = ['nama', 'jenis', 'merk', 'lokasi']
    missing = [f for f in required if not data.get(f, '').strip()]
    if missing:
        return JsonResponse(
            {'status': 'error', 'message': f'Field wajib tidak lengkap: {", ".join(missing)}'},
            status=400
        )

    jenis_input = data['jenis'].strip()
    try:
        device_type = DeviceType.objects.get(name__iexact=jenis_input)
    except DeviceType.DoesNotExist:
        tersedia = list(DeviceType.objects.values_list('name', flat=True).order_by('name'))
        return JsonResponse(
            {
                'status': 'error',
                'message': f'Jenis perangkat "{jenis_input}" tidak ditemukan di database.',
                'jenis_tersedia': tersedia,
            },
            status=400
        )

    fields = _resolve_fields(data)

    # Cari device existing by IP atau serial number
    existing = None
    if fields['ip_address']:
        existing = Device.objects.filter(
            ip_address=fields['ip_address'], is_deleted=False
        ).first()
    if not existing and fields['serial_number']:
        existing = Device.objects.filter(
            serial_number=fields['serial_number'], is_deleted=False
        ).first()

    # UPDATE jika sudah ada
    if existing:
        device_before = copy.copy(existing)
        existing.nama             = fields['nama']
        existing.jenis            = device_type
        existing.merk             = fields['merk']
        existing.type             = fields['type']
        existing.serial_number    = fields['serial_number']
        existing.firmware_version = fields['firmware_version']
        existing.ip_address       = fields['ip_address']
        existing.lokasi           = fields['lokasi']
        existing.status_operasi   = fields['status_operasi']
        existing.keterangan       = fields['keterangan']
        if fields['tahun_operasi']:
            existing.tahun_operasi = fields['tahun_operasi']
        try:
            existing.save()
            log_edit(device_before, existing, user=None)
        except IntegrityError as e:
            return JsonResponse(
                {'status': 'error', 'message': f'Gagal update: {str(e)}'},
                status=409
            )
        return JsonResponse(
            {
                'status': 'ok',
                'aksi': 'diperbarui',
                'message': f'Perangkat "{existing.nama}" diperbarui.',
                'id': existing.pk,
                'nama': existing.nama,
                'jenis': device_type.name,
                'lokasi': existing.lokasi,
                'ip_address': existing.ip_address,
            },
            status=200
        )

    # CREATE jika belum ada
    try:
        device = Device.objects.create(
            nama             = fields['nama'],
            jenis            = device_type,
            merk             = fields['merk'],
            type             = fields['type'],
            serial_number    = fields['serial_number'],
            firmware_version = fields['firmware_version'],
            ip_address       = fields['ip_address'],
            lokasi           = fields['lokasi'],
            status_operasi   = fields['status_operasi'],
            keterangan       = fields['keterangan'],
            tahun_operasi    = fields['tahun_operasi'],
            public_token     = secrets.token_urlsafe(16),
        )
        log_create(device, user=None)
    except IntegrityError as e:
        return JsonResponse(
            {'status': 'error', 'message': f'Gagal menyimpan data: {str(e)}'},
            status=409
        )

    return JsonResponse(
        {
            'status': 'ok',
            'aksi': 'ditambahkan',
            'message': 'Perangkat berhasil ditambahkan.',
            'id': device.pk,
            'nama': device.nama,
            'jenis': device_type.name,
            'lokasi': device.lokasi,
            'ip_address': device.ip_address,
        },
        status=201
    )


def _list_devices(request):
    qs = Device.objects.filter(is_deleted=False).select_related('jenis').order_by('nama')

    jenis_filter = request.GET.get('jenis', '').strip()
    if jenis_filter:
        qs = qs.filter(jenis__name__iexact=jenis_filter)

    lokasi_filter = request.GET.get('lokasi', '').strip()
    if lokasi_filter:
        qs = qs.filter(lokasi__icontains=lokasi_filter)

    devices = [
        {
            'id': d.pk,
            'nama': d.nama,
            'jenis': d.jenis.name if d.jenis else None,
            'merk': d.merk,
            'type': d.type,
            'serial_number': d.serial_number,
            'ip_address': d.ip_address,
            'lokasi': d.lokasi,
            'status_operasi': d.status_operasi,
            'tahun_operasi': d.tahun_operasi,
        }
        for d in qs
    ]
    return JsonResponse({'status': 'ok', 'count': len(devices), 'devices': devices})


@csrf_exempt
@require_api_key
@require_http_methods(["GET"])
def device_types_endpoint(request):
    types = list(DeviceType.objects.values('id', 'name').order_by('name'))
    return JsonResponse({'status': 'ok', 'count': len(types), 'device_types': types})


def ping(request):
    return JsonResponse({'status': 'ok', 'message': 'FASOP API aktif.'})

# ═══════════════════════════════════════════════════════════════════════════
#  Logsheet Pembebanan — feed untuk n8n → Google Sheets
# ═══════════════════════════════════════════════════════════════════════════
def _col_a1(n):
    """Indeks kolom 1-based -> huruf A1 (6->F, 38->AL)."""
    s = ''
    while n > 0:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


@csrf_exempt
@require_api_key
@require_http_methods(["GET"])
def logsheet_endpoint(request):
    """
    Feed nilai logsheet untuk n8n → Google Sheets.

    Query:
      tanggal=YYYY-MM-DD   (default: hari ini, zona server)
      slot=N | latest      (opsional; N=0..47, 'latest'=slot terisi terakhir.
                            tanpa slot = semua slot terisi hari itu)
      format=cells|rows    (default 'cells')

    format=cells  -> daftar datar {sheet, cell, value} (cell A1, mis. "AL7")
                     siap ditulis batch ke Google Sheets (nilai + posisi sel).
    format=rows   -> per titik {key, sheet, row, kol0, besaran, nama, nilai:{slot:val}}
    """
    import datetime
    from django.utils import timezone
    from django.db.models import Max
    from logsheet.models import LogsheetTitik, LogsheetNilai

    try:
        tanggal = datetime.date.fromisoformat(request.GET.get('tanggal', ''))
    except ValueError:
        tanggal = timezone.localdate()

    fmt = request.GET.get('format', 'cells')
    slot_param = request.GET.get('slot')

    titik = {t.id: t for t in LogsheetTitik.objects.filter(aktif=True, baris__isnull=False)
             .exclude(sheet='').exclude(baris=0)}

    qs = LogsheetNilai.objects.filter(titik_id__in=titik.keys(), tanggal=tanggal,
                                      nilai__isnull=False)
    slot = None
    if slot_param == 'latest':
        slot = qs.aggregate(m=Max('slot'))['m']
        if slot is not None:
            qs = qs.filter(slot=slot)
    elif slot_param not in (None, ''):
        try:
            slot = int(slot_param)
            qs = qs.filter(slot=slot)
        except ValueError:
            pass

    rows = list(qs.values_list('titik_id', 'slot', 'nilai'))

    def waktu_label(i):
        menit = (i + 1) * 30
        return '24:00' if menit == 1440 else f'{menit // 60:02d}:{menit % 60:02d}'

    if fmt == 'rows':
        per = {}
        for tid, s, v in rows:
            per.setdefault(tid, {})[s] = round(v, 2)
        data = []
        for tid, nilai in per.items():
            t = titik[tid]
            data.append({'key': t.key, 'sheet': t.sheet, 'row': t.baris, 'kol0': t.kol0,
                         'besaran': t.besaran, 'nama': t.nama, 'nilai': nilai})
        return JsonResponse({'status': 'ok', 'tanggal': tanggal.isoformat(),
                             'slot': slot, 'jumlah_titik': len(data),
                             'jumlah_nilai': len(rows), 'data': data})

    # format=cells
    cells = []
    for tid, s, v in rows:
        t = titik[tid]
        a1 = f'{_col_a1(t.kol0 + s)}{t.baris}'
        cells.append({'sheet': t.sheet, 'cell': a1,
                      'range': f'{t.sheet}!{a1}',   # siap untuk Google Sheets batchUpdate
                      'slot': s, 'value': round(v, 2)})
    return JsonResponse({'status': 'ok', 'tanggal': tanggal.isoformat(),
                         'slot': slot, 'waktu': waktu_label(slot) if slot is not None else None,
                         'jumlah': len(cells), 'cells': cells})


@csrf_exempt
@require_api_key
@require_http_methods(["GET"])
def logsheet_export_endpoint(request):
    """
    Unduh file .xlsx logsheet (format identik) untuk sebuah tanggal — ber-API_KEY
    agar bisa dipanggil n8n (mis. arsip harian ke NAS jam 00:05).
      ?tanggal=YYYY-MM-DD   (default: hari ini)
    """
    import datetime
    from django.utils import timezone
    from logsheet import export as xls
    try:
        tanggal = datetime.date.fromisoformat(request.GET.get('tanggal', ''))
    except ValueError:
        tanggal = timezone.localdate()
    wb = xls.build_workbook(tanggal)
    return xls.workbook_to_response(wb, f'LOGSHEET_MKS_{tanggal:%Y%m%d}.xlsx')


@csrf_exempt
@require_api_key
@require_http_methods(["GET"])
def logsheet_ranges_endpoint(request):
    """
    Daftar range A1 (per sheet, band 48 kolom) berisi sel data logsheet —
    dipakai n8n untuk Google Sheets values:batchClear (kosongkan data, format
    tetap). TRAFO punya 2 band (MW & MVAR) sehingga muncul 2 range.
    """
    from logsheet.models import LogsheetTitik
    JUMLAH_SLOT = 48
    bands = {}
    for t in (LogsheetTitik.objects.filter(aktif=True, baris__isnull=False)
              .exclude(sheet='').exclude(baris=0)):
        key = (t.sheet, t.kol0)
        b = bands.setdefault(key, [t.baris, t.baris])
        b[0] = min(b[0], t.baris)
        b[1] = max(b[1], t.baris)
    ranges = []
    for (sheet, kol0), (rmin, rmax) in bands.items():
        c1 = _col_a1(kol0)
        c2 = _col_a1(kol0 + JUMLAH_SLOT - 1)
        ranges.append(f'{sheet}!{c1}{rmin}:{c2}{rmax}')
    return JsonResponse({'status': 'ok', 'jumlah': len(ranges), 'ranges': sorted(ranges)})


# ═══════════════════════════════════════════════════════════════════════════
#  HOP (Hari Operasi Pembangkit) — terima data dari spreadsheet (n8n)
# ═══════════════════════════════════════════════════════════════════════════
def _norm_kategori_hop(raw):
    """Normalisasi teks kategori -> 'batubara' | 'bbm' | None."""
    s = (raw or '').strip().lower().replace(' ', '')
    if s in ('batubara', 'batu', 'coal', 'bb'):
        return 'batubara'
    if s in ('bbm', 'hsd', 'mfo', 'solar', 'minyak'):
        return 'bbm'
    return None


@csrf_exempt
@require_api_key
@require_http_methods(["POST"])
def hop_endpoint(request):
    """
    Terima data HOP dari spreadsheet (via n8n) -> upsert HopPembangkit + tulis
    HopSnapshot untuk tanggal tertentu. Dashboard HOP membaca snapshot terbaru.

    Body JSON:
      {
        "tanggal": "YYYY-MM-DD",         # opsional, default hari ini (zona server)
        "data": [
          {"nama": "PLTU X", "kategori": "batubara", "hop": 12.5,
           "sistem": "Sulbagsel", "aset": "PLN NP", "dmn_mw": 100, "urutan": 1},
          ...
        ]
      }

    - kategori: 'batubara'/'bbm' (toleran: 'batu bara', 'coal', 'hsd', dll).
    - hop kosong/None -> pembangkit tetap di-upsert, snapshot tanggal itu dilewati.
    - Pencocokan pembangkit: (nama, kategori). Nama baru -> dibuat (dilaporkan).
    """
    import datetime
    from django.utils import timezone
    from opsis.models import HopPembangkit, HopSnapshot

    data, err = _parse_json_body(request)
    if err:
        return err

    try:
        tanggal = datetime.date.fromisoformat(str(data.get('tanggal', '')))
    except (ValueError, TypeError):
        tanggal = timezone.localdate()

    rows = data.get('data')
    if not isinstance(rows, list):
        return JsonResponse({'status': 'error',
                             'message': "Field 'data' harus berupa array."}, status=400)

    n_snap = n_new = n_skip = 0
    dibuat, errors = [], []
    for i, r in enumerate(rows):
        if not isinstance(r, dict):
            n_skip += 1
            continue
        nama = (r.get('nama') or '').strip()
        kat  = _norm_kategori_hop(r.get('kategori'))
        if not nama or not kat:
            n_skip += 1
            if nama or r.get('kategori'):
                errors.append(f'baris {i}: nama/kategori tidak valid ({nama!r},{r.get("kategori")!r})')
            continue

        peng, created = HopPembangkit.objects.get_or_create(
            nama=nama, kategori=kat, defaults={'aktif': True})
        if created:
            n_new += 1
            dibuat.append(f'{nama} ({kat})')

        # Perbarui metadata bila dikirim (opsional)
        ubah = False
        sistem = (r.get('sistem') or '').strip()
        if sistem and sistem != peng.sistem:
            peng.sistem = sistem; ubah = True
        aset = (r.get('aset') or '').strip()
        if aset and aset != peng.aset:
            peng.aset = aset; ubah = True
        if r.get('dmn_mw') not in (None, ''):
            try:
                peng.dmn_mw = float(r['dmn_mw']); ubah = True
            except (ValueError, TypeError):
                pass
        if r.get('urutan') not in (None, ''):
            try:
                peng.urutan = int(r['urutan']); ubah = True
            except (ValueError, TypeError):
                pass
        if ubah:
            peng.save()

        # Tulis snapshot HOP bila nilainya ada
        hop_raw = r.get('hop')
        if hop_raw in (None, ''):
            continue
        try:
            hop = float(str(hop_raw).replace(',', '.'))
        except (ValueError, TypeError):
            errors.append(f'baris {i} ({nama}): hop bukan angka ({hop_raw!r})')
            continue
        HopSnapshot.objects.update_or_create(
            pembangkit=peng, tanggal=tanggal, defaults={'hop': hop})
        n_snap += 1

    return JsonResponse({
        'status': 'ok',
        'tanggal': tanggal.isoformat(),
        'snapshot_ditulis': n_snap,
        'pembangkit_baru': n_new,
        'dilewati': n_skip,
        'dibuat': dibuat,
        'errors': errors,
    })
