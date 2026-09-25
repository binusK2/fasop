import json
import secrets
import copy
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.db import IntegrityError

from devices.models import Device, DeviceType
from devices.device_audit import log_create, log_edit
from .auth import require_api_key, require_kunci_baca


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


# ═══════════════════════════════════════════════════════════════════════════
#  Prakiraan Beban — kurva 30 menit dari spreadsheet (n8n -> Google Sheets)
# ═══════════════════════════════════════════════════════════════════════════
MAX_PRAKIRAAN_ROWS = 2000   # ~40 hari x 48 titik — cukup lapang, tetap ada batas


def _norm_menit(row):
    """
    Ambil menit-sejak-00:00 dari sebuah baris. Menerima dua bentuk supaya n8n
    tidak perlu transformasi tambahan:
      {"menit": 1110}          -> 1110
      {"jam": "18:30"}         -> 1110   (alias: "waktu", "time")
    Return (menit, error_str). Kolom jam dari Google Sheets kadang terbaca
    "18:30:00" — detiknya diabaikan.
    """
    raw = row.get('menit')
    if raw not in (None, ''):
        try:
            menit = int(float(str(raw).strip().replace(',', '.')))
        except (TypeError, ValueError):
            return None, f'menit bukan angka ({raw!r})'
        if not 0 <= menit <= 1439:
            return None, f'menit di luar 0-1439 ({menit})'
        return menit, None

    jam = row.get('jam') or row.get('waktu') or row.get('time')
    if jam in (None, ''):
        return None, "tidak ada field 'menit' maupun 'jam'"
    bagian = str(jam).strip().split(':')
    if len(bagian) < 2:
        return None, f'jam bukan format HH:MM ({jam!r})'
    try:
        hh, mm = int(bagian[0]), int(bagian[1])
    except (TypeError, ValueError):
        return None, f'jam bukan format HH:MM ({jam!r})'
    if not (0 <= hh <= 23 and 0 <= mm <= 59):
        return None, f'jam di luar rentang ({jam!r})'
    return hh * 60 + mm, None


def _norm_mw(raw):
    """MW dari sel spreadsheet -> float. Toleran koma desimal ala Indonesia."""
    if raw in (None, ''):
        return None, 'mw kosong'
    try:
        return float(str(raw).strip().replace(',', '.')), None
    except (TypeError, ValueError):
        return None, f'mw bukan angka ({raw!r})'


@csrf_exempt
@require_api_key
@require_http_methods(["POST", "GET"])
def prakiraan_beban_endpoint(request):
    """
    Kurva prakiraan beban sistem (total MW) dari spreadsheet dispatcher.
    Menggantikan model ML sebagai sumber seri 'forecast' di chart Beban Kit —
    lihat opsis/prakiraan.py dan setting OPSIS_FORECAST_SOURCE.

    POST — kirim satu hari penuh (48 titik grid 30 menit):
      {
        "tanggal": "2026-08-19",        # opsional, default hari ini (zona server)
        "sumber": "spreadsheet",        # opsional, label asal data
        "replace": false,               # opsional, lihat catatan di bawah
        "data": [
          {"jam": "00:00", "mw": 812.5},
          {"jam": "00:30", "mw": 805.1},
          ...
        ]
      }

    - Titik boleh dikirim sebagai {"menit": 1110} atau {"jam": "18:30"}.
    - Tiap baris boleh membawa "tanggal" sendiri untuk mengirim beberapa hari
      sekaligus (mis. hari ini + besok dalam satu panggilan).
    - Idempoten: upsert per (tanggal, menit), jadi n8n aman dijalankan berulang.
    - "replace": true menghapus titik lain pada tanggal-tanggal yang dikirim
      yang tidak ada di payload — pakai kalau spreadsheet baru saja dirapikan
      dan ada slot yang memang harus hilang. Default false (tidak menghapus
      apa pun) supaya kiriman parsial tidak diam-diam mengosongkan kurva.

    GET ?tanggal=YYYY-MM-DD — baca balik kurva satu hari untuk verifikasi.
    """
    import datetime
    from django.utils import timezone
    from opsis.models import PrakiraanBeban

    if request.method == 'GET':
        try:
            tanggal = datetime.date.fromisoformat(str(request.GET.get('tanggal', '')))
        except (ValueError, TypeError):
            tanggal = timezone.localdate()
        rows = PrakiraanBeban.objects.filter(tanggal=tanggal).order_by('menit')
        return JsonResponse({
            'status': 'ok',
            'tanggal': tanggal.isoformat(),
            'jumlah': rows.count(),
            'data': [{'menit': r.menit, 'jam': r.jam, 'mw': r.mw,
                      'sumber': r.sumber} for r in rows],
        })

    data, err = _parse_json_body(request)
    if err:
        return err

    rows = data.get('data')
    if not isinstance(rows, list):
        return JsonResponse({'status': 'error',
                             'message': "Field 'data' harus berupa array."}, status=400)
    if len(rows) > MAX_PRAKIRAAN_ROWS:
        return JsonResponse(
            {'status': 'error',
             'message': f'Terlalu banyak baris ({len(rows)}), maksimal {MAX_PRAKIRAAN_ROWS}.'},
            status=400)

    try:
        tanggal_default = datetime.date.fromisoformat(str(data.get('tanggal', '')))
    except (ValueError, TypeError):
        tanggal_default = timezone.localdate()

    sumber = (data.get('sumber') or 'spreadsheet').strip()[:50] or 'spreadsheet'
    replace = bool(data.get('replace'))

    n_tulis = n_skip = 0
    errors = []
    terkirim = {}    # tanggal -> set(menit) yang berhasil ditulis
    for i, r in enumerate(rows):
        if not isinstance(r, dict):
            n_skip += 1
            continue

        tanggal = tanggal_default
        if r.get('tanggal'):
            try:
                tanggal = datetime.date.fromisoformat(str(r['tanggal']).strip())
            except (ValueError, TypeError):
                n_skip += 1
                errors.append(f'baris {i}: tanggal tidak valid ({r["tanggal"]!r})')
                continue

        menit, e = _norm_menit(r)
        if e:
            n_skip += 1
            errors.append(f'baris {i}: {e}')
            continue

        mw, e = _norm_mw(r.get('mw'))
        if e:
            # Sel kosong itu wajar (slot yang belum diisi dispatcher) — dilewati
            # diam-diam, tidak dilaporkan sebagai error.
            n_skip += 1
            if r.get('mw') not in (None, ''):
                errors.append(f'baris {i}: {e}')
            continue

        PrakiraanBeban.objects.update_or_create(
            tanggal=tanggal, menit=menit,
            defaults={'mw': mw, 'sumber': sumber})
        terkirim.setdefault(tanggal, set()).add(menit)
        n_tulis += 1

    n_hapus = 0
    if replace and terkirim:
        for tanggal, menit_set in terkirim.items():
            n_hapus += PrakiraanBeban.objects.filter(tanggal=tanggal).exclude(
                menit__in=menit_set).delete()[0]

    return JsonResponse({
        'status': 'ok',
        'tanggal': tanggal_default.isoformat(),
        'tanggal_tertulis': sorted(t.isoformat() for t in terkirim),
        'titik_ditulis': n_tulis,
        'titik_dihapus': n_hapus,
        'dilewati': n_skip,
        'errors': errors[:50],
    })


# ═══════════════════════════════════════════════════════════════════════════
#  Endpoint BACA untuk konsumen luar — dikunci devices.KunciApi + DatasetApi
#
#  Aturan yang berlaku untuk SEMUA endpoint di blok ini:
#
#  1. Angkanya wajib lewat modul bersama (opsis/ktt.py, opsis/beban_kit.py,
#     opsis/freq_history.py), tidak pernah disalin ke sini. Kalau disalin,
#     layar ruang kontrol dan spreadsheet pihak luar bisa menyebut angka
#     berbeda untuk hal yang sama.
#  2. "Tidak tahu" tidak pernah dikirim sebagai nol. Historian mati dibalas
#     503; nol yang terlanjur tercatat di spreadsheet konsumen tidak akan
#     pernah diperbaiki.
#  3. Rentang waktu selalu dibatasi. Satu permintaan tidak boleh menahan satu
#     worker gunicorn sampai timeout.
# ═══════════════════════════════════════════════════════════════════════════
MAKS_JAM_FREKUENSI = 6          # 1 baris/detik → 6 jam ≈ 21.600 titik

SATUAN_BESARAN = {'mw': 'MW', 'mvar': 'MVAR', 'amp': 'A', 'volt': 'kV'}


def _galat(pesan, status=400, **extra):
    return JsonResponse(dict({'status': 'error', 'message': pesan}, **extra), status=status)


def _jam_slot(i):
    """Label jam sebuah slot logsheet: 0 -> '00:30', 47 -> '24:00'."""
    if i is None:
        return None
    menit = (i + 1) * 30
    return '24:00' if menit == 1440 else f'{menit // 60:02d}:{menit % 60:02d}'


def _tanggal(request, nama='tanggal'):
    """Tanggal dari query string. Kosong = hari ini. Salah format = None."""
    import datetime
    from django.utils import timezone
    mentah = (request.GET.get(nama) or '').strip()
    if not mentah:
        return timezone.localdate()
    try:
        return datetime.date.fromisoformat(mentah)
    except ValueError:
        return None


def _waktu(request, nama):
    """
    Datetime aware dari query string ISO ('2026-09-21T08:00' atau dengan offset).

    Return (nilai, galat). Nilai None tanpa galat berarti parameternya memang
    tidak dikirim — pemanggil yang menentukan bawaannya.
    """
    import datetime
    from django.utils import timezone
    mentah = (request.GET.get(nama) or '').strip()
    if not mentah:
        return None, None
    try:
        t = datetime.datetime.fromisoformat(mentah)
    except ValueError:
        return None, f'Parameter "{nama}" harus waktu ISO, mis. 2026-09-21T08:00.'
    if timezone.is_naive(t):
        t = timezone.make_aware(t)
    return t, None


def _rentang(request, bawaan_menit, maks_menit):
    """
    Rentang (t0, t1) aware dari ?dari=&sampai=, dengan batas atas lebarnya.

    Return (t0, t1, galat). `sampai` kosong = sekarang; `dari` kosong =
    `sampai` dikurangi `bawaan_menit`.
    """
    import datetime
    from django.utils import timezone

    t1, galat = _waktu(request, 'sampai')
    if galat:
        return None, None, galat
    t0, galat = _waktu(request, 'dari')
    if galat:
        return None, None, galat

    if t1 is None:
        t1 = timezone.localtime()
    if t0 is None:
        t0 = t1 - datetime.timedelta(minutes=bawaan_menit)
    if t0 >= t1:
        return None, None, 'Parameter "dari" harus lebih awal dari "sampai".'

    lebar_jam = (t1 - t0).total_seconds() / 3600
    if lebar_jam * 60 > maks_menit:
        return None, None, (
            f'Rentang terlalu lebar ({lebar_jam:.1f} jam). '
            f'Maksimum {maks_menit / 60:.0f} jam sekali permintaan — '
            f'ambil bertahap bila butuh lebih panjang.'
        )
    return t0, t1, None


# ── Beban KTT ───────────────────────────────────────────────────────────────
@csrf_exempt
@require_kunci_baca('beban_ktt')
@require_http_methods(["GET"])
def opsis_beban_ktt_endpoint(request):
    """
    Beban konsumen tegangan tinggi terkini.

    Angkanya lewat opsis.ktt.baca_beban_ktt() — sumber dan cache yang sama
    persis dengan halaman /opsis/beban-ktt/, jadi penarik dari luar tidak
    menambah query ke MSSQL selama halamannya juga terbuka, dan tidak mungkin
    menyebut nama konsumen berbeda dari layar FASOP.
    """
    from django.utils import timezone
    from opsis import ktt

    data = ktt.baca_beban_ktt()
    rows = data['rows']

    # Historian tak terjangkau → get_beban_ktt() mengembalikan daftar kosong dan
    # total jatuh ke 0. JANGAN kirim angka 0 itu: bagi konsumen luar 0 MW tidak
    # bisa dibedakan dari "semua konsumen KTT sedang padam", dan sekali tercatat
    # di spreadsheet mereka, angka palsu itu tidak akan pernah diperbaiki.
    if not rows:
        return JsonResponse({
            'status':   'error',
            'message':  'Data beban KTT sedang tidak tersedia (historian SCADA tidak terjangkau).',
            'terputus': True,
        }, status=503)

    return JsonResponse({
        'status':   'ok',
        'dataset':  'beban_ktt',
        'waktu':    timezone.localtime().isoformat(),
        'sumber':   'OPSIS — IND_LOAD (historian SCADA)',
        'satuan':   'MW',
        'terputus': data['terputus'],
        'total_mw': data['total_mw'],
        'jumlah':   data['jumlah'],
        'konsumen': [
            {
                'kode': r['analog'],
                'nama': r.get('nama') or r['analog'],
                'mw':   r['value'],
            }
            for r in rows
        ],
    })


# ── Beban pembangkit — terkini ──────────────────────────────────────────────
@csrf_exempt
@require_kunci_baca('beban_pembangkit')
@require_http_methods(["GET"])
def opsis_beban_pembangkit_endpoint(request):
    """
    MW/MVAR terkini tiap pembangkit aktif, beserta rincian per unit.

    ?unit=0  — hilangkan rincian unit (balasan jauh lebih kecil bila yang
               dibutuhkan hanya total per pembangkit).
    """
    from django.utils import timezone
    from opsis import beban_kit

    data = beban_kit.baca_live()
    rows = data['rows']

    # Aturan yang sama dengan beban KTT: historian mati dibalas 503, bukan
    # daftar berisi null yang di sisi konsumen gampang jatuh jadi nol.
    if data['terputus'] or not rows:
        return _galat(
            'Data beban pembangkit sedang tidak tersedia '
            '(historian SCADA tidak terjangkau).',
            status=503, dataset='beban_pembangkit', terputus=True,
        )

    sertakan_unit = request.GET.get('unit') != '0'

    pembangkit = []
    for r in rows:
        item = {
            'kode':       r['kode'],
            'nama':       r['nama'],
            'jenis':      r['jenis'],
            'mw':         r['mw'],
            'mvar':       r['mvar'],
            'diragukan':  r['diragukan'],
            'keterangan': r['keterangan'],
        }
        if sertakan_unit:
            item['unit'] = [
                {'nama': u.get('nama'), 'mw': u.get('mw'), 'mvar': u.get('mvar')}
                for u in r['units']
            ]
        pembangkit.append(item)

    return JsonResponse({
        'status':           'ok',
        'dataset':          'beban_pembangkit',
        'waktu':            timezone.localtime().isoformat(),
        'sumber':           'OPSIS — sumber KIT realtime (historian SCADA)',
        'satuan':           {'mw': 'MW', 'mvar': 'MVAR', 'frekuensi': 'Hz'},
        'terputus':         False,
        'frekuensi_sistem': data['frekuensi_sistem'],
        'total_mw':         data['total_mw'],
        'jumlah':           data['jumlah'],
        'pembangkit':       pembangkit,
    })


# ── Beban pembangkit — riwayat ──────────────────────────────────────────────
@csrf_exempt
@require_kunci_baca('beban_pembangkit')
@require_http_methods(["GET"])
def opsis_beban_pembangkit_riwayat_endpoint(request):
    """
    Riwayat MW/MVAR per menit dari snapshot PostgreSQL (opsis.SnapLive).

    ?dari=&sampai=  waktu ISO (bawaan: 60 menit terakhir)
    ?kode=          daftar kode pembangkit dipisah koma (bawaan: semua aktif)

    Sumbernya PostgreSQL, bukan MSSQL — jadi endpoint ini tetap menjawab saat
    historian tak terjangkau, dan menariknya tidak membebani historian yang
    dipakai bersama ruang kontrol. Konsekuensinya nilai paling baru bisa
    tertinggal sampai satu menit (cron collect_live berjalan tiap menit); yang
    butuh angka detik ini memakai endpoint terkini di atas.
    """
    from opsis import beban_kit

    t0, t1, galat = _rentang(request, bawaan_menit=60,
                             maks_menit=beban_kit.MAKS_HARI_RIWAYAT * 24 * 60)
    if galat:
        return _galat(galat, dataset='beban_pembangkit')

    kode = [k.strip().upper() for k in (request.GET.get('kode') or '').split(',') if k.strip()]
    data = beban_kit.riwayat(t0, t1, kode or None)

    if kode and not data:
        return _galat(
            f'Tidak ada pembangkit aktif dengan kode {", ".join(kode)}.',
            status=404, dataset='beban_pembangkit',
        )

    return JsonResponse({
        'status':     'ok',
        'dataset':    'beban_pembangkit',
        'dari':       t0.isoformat(),
        'sampai':     t1.isoformat(),
        'sumber':     'opsis.SnapLive (snapshot PostgreSQL, 1 titik per menit)',
        'satuan':     {'mw': 'MW', 'mvar': 'MVAR', 'hz': 'Hz'},
        'jumlah':     sum(d['jumlah'] for d in data),
        'pembangkit': data,
    })


# ── Beban trafo — terkini ───────────────────────────────────────────────────
@csrf_exempt
@require_kunci_baca('beban_trafo')
@require_http_methods(["GET"])
def opsis_beban_trafo_endpoint(request):
    """
    Daya terkini tiap trafo, dikelompokkan per GI.

    ?jenis=distribusi (bawaan) | ibt

    Angkanya lewat opsis.trafo.baca_live() — sumber, penyaring trafo aktif, dan
    cache yang sama persis dengan halaman /opsis/beban-trafo/, jadi penarik dari
    luar tidak menambah query ke MSSQL selama halamannya juga terbuka, dan tidak
    mungkin menyebut GI/bay berbeda dari layar FASOP.

    Nilai per trafo dikirim APA ADANYA (p bisa negatif — arah aliran daya lewat
    IBT dua arah). `total_mw` dan `site_totals` sebaliknya memakai magnitudo,
    menyamai kartu total di layar: menjumlahkan bertanda akan membuat dua trafo
    berlawanan arah saling meniadakan dan GI yang sibuk terlihat nyaris kosong.
    """
    from django.utils import timezone
    from opsis import trafo as trafo_io

    jenis, galat = trafo_io.normalkan_jenis(request.GET.get('jenis'))
    if galat:
        return _galat(galat, dataset='beban_trafo')

    data = trafo_io.baca_live(jenis)

    # Aturan yang sama dengan beban KTT dan beban pembangkit: historian mati
    # dibalas 503, bukan daftar kosong yang di sisi konsumen gampang jatuh jadi
    # nol — dan nol tidak bisa dibedakan dari "semua trafo padam".
    if data['terputus'] or not data['rows']:
        return _galat(
            'Data beban trafo sedang tidak tersedia '
            '(historian SCADA tidak terjangkau).',
            status=503, dataset='beban_trafo', terputus=True,
        )

    return JsonResponse({
        'status':   'ok',
        'dataset':  'beban_trafo',
        'jenis':    jenis,
        'waktu':    timezone.localtime().isoformat(),
        'sumber':   'OPSIS — ALL_TRANS_DATA (historian SCADA)',
        'satuan':   {'p': 'MW', 'q': 'MVAR', 'v': 'kV', 'i': 'A'},
        'terputus': False,
        'total_mw': data['total_mw'],
        'jumlah':   data['jumlah'],
        'gi': [
            {
                'site':     site,
                'total_mw': data['site_totals'].get(site),
                'trafo': [
                    {'bay': r['bay'], 'p': r['p'], 'q': r['q'],
                     'v': r['v'], 'i': r['i']}
                    for r in daftar
                ],
            }
            for site, daftar in data['grouped'].items()
        ],
    })


# ── Beban trafo — riwayat ───────────────────────────────────────────────────
@csrf_exempt
@require_kunci_baca('beban_trafo')
@require_http_methods(["GET"])
def opsis_beban_trafo_riwayat_endpoint(request):
    """
    Riwayat daya aktif (P) per menit dari snapshot PostgreSQL (opsis.SnapTrafo).

    ?jenis=distribusi (bawaan) | ibt
    ?dari=&sampai=  waktu ISO (bawaan: 60 menit terakhir)
    ?site=          daftar nama GI dipisah koma (bawaan: semua)

    Hanya P yang tersedia — SnapTrafo memang hanya menyimpan itu; Q/V/I cuma ada
    pada endpoint terkini. Sumbernya PostgreSQL, jadi endpoint ini tetap menjawab
    saat historian tak terjangkau, dan menariknya tidak membebani historian yang
    dipakai bersama ruang kontrol.
    """
    from opsis import trafo as trafo_io

    jenis, galat = trafo_io.normalkan_jenis(request.GET.get('jenis'))
    if galat:
        return _galat(galat, dataset='beban_trafo')

    t0, t1, galat = _rentang(request, bawaan_menit=60,
                             maks_menit=trafo_io.MAKS_HARI_RIWAYAT * 24 * 60)
    if galat:
        return _galat(galat, dataset='beban_trafo')

    site = [s.strip() for s in (request.GET.get('site') or '').split(',') if s.strip()]
    data = trafo_io.riwayat(t0, t1, jenis, site or None)

    if site and not data:
        return _galat(
            f'Tidak ada trafo {jenis} aktif di GI {", ".join(site)}.',
            status=404, dataset='beban_trafo',
        )

    return JsonResponse({
        'status':  'ok',
        'dataset': 'beban_trafo',
        'jenis':   jenis,
        'dari':    t0.isoformat(),
        'sampai':  t1.isoformat(),
        'sumber':  'opsis.SnapTrafo (snapshot PostgreSQL, 1 titik per menit)',
        'satuan':  {'p': 'MW'},
        'jumlah':  sum(d['jumlah'] for d in data),
        'trafo':   data,
    })


# ── Frekuensi sistem ────────────────────────────────────────────────────────
@csrf_exempt
@require_kunci_baca('frekuensi')
@require_http_methods(["GET"])
def opsis_frekuensi_endpoint(request):
    """
    Riwayat frekuensi sistem per detik.

    ?dari=&sampai=  waktu ISO (bawaan: 60 menit terakhir, maksimum 6 jam)

    Lewat opsis.freq_history — BUKAN mssql.get_freq_range() langsung. Modul itu
    menggabungkan tiga sumber (historian SYS_FREQ_HIS, cerminnya SnapFreq, dan
    rekaman FASOP sendiri SnapFreqRT) menurut prioritas, sehingga deretnya tetap
    terisi saat job penulis historian berhenti — kejadian yang pernah memadamkan
    seluruh analisis Respons Pembangkit selama ±42 jam tanpa ketahuan.

    `sumber_rincian` menyebut berapa detik diambil dari masing-masing sumber.
    Angka itu sengaja ikut dikirim: konsumen yang memakai deret ini untuk
    analisis berhak tahu bagian mana yang ditambal, bukan cuma menerima garis
    yang terlihat mulus.
    """
    from django.utils import timezone
    from opsis import freq_history

    t0, t1, galat = _rentang(request, bawaan_menit=60,
                             maks_menit=MAKS_JAM_FREKUENSI * 60)
    if galat:
        return _galat(galat, dataset='frekuensi')

    # freq_history bekerja dengan datetime naive waktu lokal (MSSQL mengembalikan
    # naive, PostgreSQL aware — modul itu yang menyamakannya).
    deret, info = freq_history.ambil_range_detail(
        timezone.localtime(t0).replace(tzinfo=None),
        timezone.localtime(t1).replace(tzinfo=None),
    )

    return JsonResponse({
        'status':         'ok',
        'dataset':        'frekuensi',
        'dari':           t0.isoformat(),
        'sampai':         t1.isoformat(),
        'satuan':         'Hz',
        'sumber':         info.get('sumber'),
        'sumber_teks':    freq_history.keterangan(info),
        'sumber_rincian': {k: info.get(k, 0) for k in ('historian', 'snapfreq', 'postgres')},
        'jumlah':         len(deret),
        # Rentang yang memang sepi dibalas 200 dengan deret kosong, bukan 503:
        # pertanyaan "apakah datanya memang tidak ada" adalah jawaban yang sah,
        # berbeda dari endpoint terkini yang kekosongannya selalu berarti rusak.
        'deret': [
            {'waktu': timezone.make_aware(t).isoformat(), 'hz': hz}
            for t, hz in deret
        ],
    })


# ── Logsheet pembebanan ─────────────────────────────────────────────────────
@csrf_exempt
@require_kunci_baca('logsheet')
@require_http_methods(["GET"])
def logsheet_pembebanan_endpoint(request):
    """
    Nilai logsheet pembebanan per slot 30 menit untuk satu tanggal.

    ?tanggal=YYYY-MM-DD  (bawaan: hari ini)
    ?kategori=kit|transmisi|busbar|trafo
    ?besaran=mw|mvar|amp|volt
    ?slot=N|latest       (N = 0..47; 'latest' = slot terisi terakhir)

    Berbeda dari /api/v1/logsheet/ (feed internal n8n), endpoint ini TIDAK
    mengirim sheet/baris/kolom template Excel maupun pemetaan MSSQL-nya. Dua
    alasan: posisi sel adalah urusan berkas ekspor FASOP dan bisa berubah kapan
    saja tanpa mengubah arti datanya, sedangkan nama tabel/kolom historian
    adalah rincian infrastruktur SCADA yang tidak ada gunanya di luar. Konsumen
    memakai `key` sebagai identitas titik.

    Juga berbeda: titik yang belum punya posisi ekspor tetap ikut di sini. Feed
    internal menyaringnya karena tidak ada sel untuk diisi; di sini nilainya
    tetap data yang sah.
    """
    from django.db.models import Max
    from logsheet.models import LogsheetNilai, LogsheetTitik

    tanggal = _tanggal(request)
    if tanggal is None:
        return _galat('Parameter "tanggal" harus YYYY-MM-DD.', dataset='logsheet')

    qs_titik = LogsheetTitik.objects.filter(aktif=True)

    kategori = (request.GET.get('kategori') or '').strip().lower()
    if kategori:
        sah = {k for k, _ in LogsheetTitik._meta.get_field('kategori').choices}
        if kategori not in sah:
            return _galat(f'Kategori "{kategori}" tidak dikenal. Pilihan: '
                          f'{", ".join(sorted(sah))}.', dataset='logsheet')
        qs_titik = qs_titik.filter(kategori=kategori)

    besaran = (request.GET.get('besaran') or '').strip().lower()
    if besaran:
        if besaran not in SATUAN_BESARAN:
            return _galat(f'Besaran "{besaran}" tidak dikenal. Pilihan: '
                          f'{", ".join(sorted(SATUAN_BESARAN))}.', dataset='logsheet')
        qs_titik = qs_titik.filter(besaran=besaran)

    titik = {t.id: t for t in qs_titik}
    if not titik:
        return _galat('Tidak ada titik logsheet yang cocok dengan penyaringnya.',
                      status=404, dataset='logsheet')

    qs = LogsheetNilai.objects.filter(titik_id__in=titik.keys(), tanggal=tanggal,
                                      nilai__isnull=False)

    slot_param = (request.GET.get('slot') or '').strip().lower()
    slot = None
    if slot_param == 'latest':
        slot = qs.aggregate(m=Max('slot'))['m']
        qs = qs.filter(slot=slot) if slot is not None else qs.none()
    elif slot_param:
        try:
            slot = int(slot_param)
        except ValueError:
            return _galat('Parameter "slot" harus angka 0..47 atau "latest".',
                          dataset='logsheet')
        if not 0 <= slot <= 47:
            return _galat('Parameter "slot" harus 0..47 (0 = 00:30, 47 = 24:00).',
                          dataset='logsheet')
        qs = qs.filter(slot=slot)

    per = {}
    for tid, s, v in qs.values_list('titik_id', 'slot', 'nilai'):
        per.setdefault(tid, []).append({'slot': s, 'waktu': _jam_slot(s),
                                        'nilai': round(v, 2)})

    data = []
    for tid, t in sorted(titik.items(), key=lambda kv: (kv[1].kategori, kv[1].key)):
        nilai = sorted(per.get(tid, []), key=lambda n: n['slot'])
        data.append({
            'key':      t.key,
            'nama':     t.nama or t.key,
            'kategori': t.kategori,
            'besaran':  t.besaran,
            'satuan':   SATUAN_BESARAN.get(t.besaran, ''),
            'jumlah':   len(nilai),
            'nilai':    nilai,
        })

    return JsonResponse({
        'status':       'ok',
        'dataset':      'logsheet',
        'tanggal':      tanggal.isoformat(),
        'slot':         slot,
        'waktu_slot':   _jam_slot(slot) if slot is not None else None,
        'sumber':       'logsheet.LogsheetNilai (slot 30 menit, diisi cron collect_logsheet)',
        'jumlah_titik': len(data),
        'jumlah_nilai': sum(d['jumlah'] for d in data),
        'titik':        data,
    })


# ═══════════════════════════════════════════════════════════════════════════
#  Data FASOP (bukan OPSIS)
#
#  Konsumen pertamanya bot WhatsApp (deploy/WA_BOT_OLLAMA.md): n8n menarik
#  endpoint ini, meringkasnya jadi teks, lalu LLM lokal menjawab HANYA dari
#  teks itu. Karena itu balasannya sengaja sudah berisi angka jadi (jumlah,
#  durasi, progres) — model 7B tidak bisa diandalkan untuk berhitung sendiri,
#  dan angka yang ia karang terbaca sama meyakinkannya dengan angka asli.
# ═══════════════════════════════════════════════════════════════════════════

MAKS_DAFTAR_MONITOR = 50        # RTU DOWN / host PROBLEM yang dirinci per bagian
MAKS_PEMELIHARAAN_OPEN = 30
MAKS_HASIL_PERALATAN = 20
MAKS_KATA_CARI = 6


def _waktu_lokal(dt):
    from django.utils import timezone
    return timezone.localtime(dt).isoformat() if dt else None


# ── Status RTU & Zabbix ─────────────────────────────────────────────────────
@csrf_exempt
@require_kunci_baca('status_monitor')
@require_http_methods(["GET"])
def fasop_status_monitor_endpoint(request):
    """
    Status terkini RTU dan host Zabbix — isi yang sama dengan /device-mon/.

    Hanya RTU/host yang `aktif` (sama dengan dashboard), dan hanya instansi
    Zabbix yang aktif. Penggolongan OK/warning/problem memakai
    device_mon.zabbix_api.state_class() — kalau disalin, ambang "kritis" di
    sini dan di layar Device Monitor bisa berbeda tanpa ada yang sadar.

    `sinkron_terakhir` per instansi ikut dikirim: status host hanya sesegar
    cron sync_zabbix terakhir, dan "0 host bermasalah" dari data yang sudah
    basi sejam berbeda arti dengan "0 host bermasalah" barusan.
    """
    from django.utils import timezone
    from device_mon.models import RTU, ZabbixInstance
    from device_mon.zabbix_api import severity_index, state_class

    rtus = list(RTU.objects.filter(aktif=True))
    hitung_rtu = {'UP': 0, 'DOWN': 0, 'UNKNOWN': 0}
    for r in rtus:
        hitung_rtu[r.state if r.state in hitung_rtu else 'UNKNOWN'] += 1

    # Yang paling lama DOWN di atas — itu yang paling perlu ditindaklanjuti.
    rtu_down = sorted((r for r in rtus if r.state == 'DOWN'),
                      key=lambda r: -(r.durasi_menit or 0))

    zabbix = []
    for inst in ZabbixInstance.objects.filter(aktif=True).order_by('urutan', 'nama'):
        hosts = list(inst.hosts.filter(aktif=True).select_related('lokasi'))
        hitung = {'ok': 0, 'warning': 0, 'problem': 0, 'unknown': 0}
        for h in hosts:
            hitung[state_class(h.state, h.severity)] += 1

        bermasalah = sorted(
            (h for h in hosts if h.state == 'PROBLEM'),
            key=lambda h: (-severity_index(h.severity), -(h.durasi_menit or 0)),
        )
        sinkron = max((h.last_synced_at for h in hosts if h.last_synced_at), default=None)
        zabbix.append({
            'kode':             inst.kode,
            'nama':             inst.nama,
            'jumlah_host':      len(hosts),
            'ok':               hitung['ok'],
            'warning':          hitung['warning'],
            'problem':          hitung['problem'],
            'unknown':          hitung['unknown'],
            'sinkron_terakhir': _waktu_lokal(sinkron),
            'host_bermasalah': [
                {
                    'nama':         h.nama,
                    'lokasi':       h.lokasi.nama if h.lokasi else '',
                    'severity':     h.severity,
                    'problem':      h.problem_name,
                    'sejak':        _waktu_lokal(h.state_sejak),
                    'durasi_menit': h.durasi_menit,
                }
                for h in bermasalah[:MAKS_DAFTAR_MONITOR]
            ],
            'host_bermasalah_terpotong': len(bermasalah) > MAKS_DAFTAR_MONITOR,
        })

    return JsonResponse({
        'status':  'ok',
        'dataset': 'status_monitor',
        'waktu':   timezone.localtime().isoformat(),
        'sumber':  'FASOP — Device Monitor (device_mon)',
        'rtu': {
            'jumlah':  len(rtus),
            'up':      hitung_rtu['UP'],
            'down':    hitung_rtu['DOWN'],
            'unknown': hitung_rtu['UNKNOWN'],
            'daftar_down': [
                {
                    'nama':         r.nama,
                    'lokasi':       r.lokasi,
                    'sejak':        _waktu_lokal(r.state_sejak),
                    'durasi_menit': r.durasi_menit,
                }
                for r in rtu_down[:MAKS_DAFTAR_MONITOR]
            ],
            'daftar_down_terpotong': len(rtu_down) > MAKS_DAFTAR_MONITOR,
        },
        'zabbix': zabbix,
    })


# ── Pemeliharaan & jadwal ───────────────────────────────────────────────────
def _bulan(request):
    """?bulan=YYYY-MM → (tahun, bulan); bawaan bulan berjalan. None bila salah."""
    from django.utils import timezone
    raw = (request.GET.get('bulan') or '').strip()
    if not raw:
        hari_ini = timezone.localdate()
        return hari_ini.year, hari_ini.month
    try:
        th, bl = raw.split('-')
        th, bl = int(th), int(bl)
    except ValueError:
        return None
    return (th, bl) if 1 <= bl <= 12 and 2000 <= th <= 2100 else None


@csrf_exempt
@require_kunci_baca('pemeliharaan')
@require_http_methods(["GET"])
def fasop_pemeliharaan_endpoint(request):
    """
    Pemeliharaan yang masih Open, rekap sebulan, dan jadwal kunjungan.

    ?bulan=YYYY-MM  (bawaan: bulan berjalan) — berlaku untuk rekap & jadwal;
                    daftar Open selalu keadaan SAAT INI, tidak ikut bulan.

    Memakai Maintenance.objects (manager yang sudah membuang soft-delete),
    dan progres jadwal dari JadwalKunjungan.get_progress() — sumber yang sama
    dengan halaman /jadwal/, termasuk pengecualian jenis peralatannya.
    """
    import datetime
    from django.db.models import Count
    from django.utils import timezone
    from jadwal.models import JadwalKunjungan
    from maintenance.models import Maintenance

    bulan = _bulan(request)
    if bulan is None:
        return _galat('Parameter "bulan" harus YYYY-MM.', dataset='pemeliharaan')
    th, bl = bulan

    # Rentang datetime, bukan lookup __month/__year: yang terakhir membungkus
    # kolom dalam fungsi sehingga indeks (status, -date) tidak terpakai.
    tz = timezone.get_current_timezone()
    awal = timezone.make_aware(datetime.datetime(th, bl, 1), tz)
    akhir = timezone.make_aware(
        datetime.datetime(th + (bl == 12), bl % 12 + 1, 1), tz)

    qs_open = Maintenance.objects.filter(status='Open')
    jumlah_open = qs_open.count()
    daftar_open = list(qs_open.select_related('device', 'device__jenis')
                       .order_by('-date')[:MAKS_PEMELIHARAAN_OPEN])

    rekap = {'preventive': {'open': 0, 'done': 0}, 'corrective': {'open': 0, 'done': 0}}
    for baris in (Maintenance.objects.filter(date__gte=awal, date__lt=akhir)
                  .values('maintenance_type', 'status').annotate(n=Count('id'))):
        tipe = (baris['maintenance_type'] or '').lower()
        st = (baris['status'] or '').lower()
        if tipe in rekap and st in rekap[tipe]:
            rekap[tipe][st] = baris['n']

    jadwal = []
    for j in JadwalKunjungan.objects.filter(tahun_rencana=th, bulan_rencana=bl):
        prog = j.get_progress()
        jadwal.append({
            'lokasi':           j.lokasi,
            'minggu':           j.minggu_rencana or None,
            'status':           j.get_status_display(),
            'jumlah_peralatan': prog['total'],
            'sudah_dipelihara': prog['selesai'],
            'progres_persen':   prog['pct'],
        })

    return JsonResponse({
        'status':  'ok',
        'dataset': 'pemeliharaan',
        'waktu':   timezone.localtime().isoformat(),
        'bulan':   f'{th}-{bl:02d}',
        'sumber':  'FASOP — maintenance.Maintenance + jadwal.JadwalKunjungan',
        'open': {
            'jumlah': jumlah_open,
            'daftar': [
                {
                    'peralatan': m.device.nama,
                    'jenis':     m.device.jenis.name if m.device.jenis else '',
                    'lokasi':    m.device.lokasi,
                    'tipe':      m.maintenance_type,
                    'tanggal':   _waktu_lokal(m.date),
                    'sudah_ttd': m.signed_by_id is not None,
                }
                for m in daftar_open
            ],
            'terpotong': jumlah_open > MAKS_PEMELIHARAAN_OPEN,
        },
        'rekap_bulan': rekap,
        'jadwal':      jadwal,
    })


# ── Pencarian peralatan ─────────────────────────────────────────────────────
_FIELD_CARI = ('nama', 'lokasi', 'merk', 'type', 'jenis__name')


def _q_kata(kata):
    from django.db.models import Q
    q = Q()
    for f in _FIELD_CARI:
        q |= Q(**{f'{f}__icontains': kata})
    return q


@csrf_exempt
@require_kunci_baca('peralatan')
@require_http_methods(["GET"])
def fasop_peralatan_endpoint(request):
    """
    Cari peralatan menurut nama / lokasi / merk / tipe / jenis.

    ?q=        kata kunci, dipisah spasi (mis. "tello rtu")
    ?lokasi=   penyaring lokasi (mengandung teks ini)
    ?hi=0      lewati perhitungan Health Index (lebih cepat)

    Tiap kata di `q` harus cocok di salah satu kolom (AND antar kata). Kalau
    hasilnya kosong dan kata lebih dari satu, diulang dengan OR — `cocok` di
    balasan menyebut mana yang terjadi. Alasannya: penanya bot mengetik
    kalimat, bukan kata kunci, dan satu kata sisa ("tolong", "dong") yang lolos
    penyaring di n8n tidak boleh membuat jawabannya "tidak ada".

    Sengaja TIDAK dikirim: ip_address, serial_number, spesifikasi, token QR.
    Itu rincian infrastruktur/aset yang tidak ada gunanya di luar FASOP dan,
    sekali terkirim ke chat WhatsApp, tidak bisa ditarik kembali.
    """
    from django.db.models import Count
    from django.utils import timezone
    from health_index.calculator import calculate_hi
    from health_index.models import KonfigurasiHI

    q = (request.GET.get('q') or '').strip()
    lokasi = (request.GET.get('lokasi') or '').strip()
    if not q and not lokasi:
        return _galat('Isi parameter "q" (kata kunci) atau "lokasi".', dataset='peralatan')

    kata = []
    for k in q.replace(',', ' ').split():
        if len(k) >= 2 and k.lower() not in {x.lower() for x in kata}:
            kata.append(k)
    kata = kata[:MAKS_KATA_CARI]

    dasar = Device.objects.filter(is_deleted=False).select_related('jenis')
    if lokasi:
        dasar = dasar.filter(lokasi__icontains=lokasi)

    qs, cocok = dasar, 'semua_kata'
    for k in kata:
        qs = qs.filter(_q_kata(k))
    if len(kata) > 1 and not qs.exists():
        atau = _q_kata(kata[0])
        for k in kata[1:]:
            atau |= _q_kata(k)
        qs, cocok = dasar.filter(atau), 'sebagian_kata'

    jumlah = qs.count()
    per_jenis = {
        (b['jenis__name'] or 'Tanpa jenis'): b['n']
        for b in qs.values('jenis__name').annotate(n=Count('id')).order_by('-n')
    }
    label_status = dict(Device.STATUS_CHOICES)
    per_status = {
        label_status.get(b['status_operasi'], b['status_operasi']): b['n']
        for b in qs.values('status_operasi').annotate(n=Count('id'))
    }

    hitung_hi = request.GET.get('hi') != '0'
    configs = KonfigurasiHI.get_or_init() if hitung_hi else None
    tahun_ini = timezone.localdate().year

    hasil = []
    for d in qs.order_by('lokasi', 'nama')[:MAKS_HASIL_PERALATAN]:
        item = {
            'nama':           d.nama,
            'jenis':          d.jenis.name if d.jenis else '',
            'merk':           d.merk,
            'tipe':           d.type or '',
            'lokasi':         d.lokasi,
            'status_operasi': d.get_status_operasi_display(),
            'tahun_operasi':  d.tahun_operasi,
            'umur_tahun':     (tahun_ini - d.tahun_operasi) if d.tahun_operasi else None,
        }
        if hitung_hi:
            # Satu peralatan yang gagal dihitung (data setengah jadi) tidak
            # boleh menjatuhkan seluruh jawaban — ia tampil tanpa HI saja.
            try:
                hi = calculate_hi(d, save_snapshot=False, configs=configs)
                item['health_index'] = hi['score']
                item['kategori_hi'] = hi['kategori']['label']
            except Exception:
                item['health_index'] = None
                item['kategori_hi'] = None
        hasil.append(item)

    return JsonResponse({
        'status':     'ok',
        'dataset':    'peralatan',
        'waktu':      timezone.localtime().isoformat(),
        'sumber':     'FASOP — devices.Device + health_index',
        'q':          q,
        'kata':       kata,
        'cocok':      cocok,
        'jumlah':     jumlah,
        'per_jenis':  per_jenis,
        'per_status': per_status,
        'terpotong':  jumlah > MAKS_HASIL_PERALATAN,
        'peralatan':  hasil,
    })
