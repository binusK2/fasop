import json
import secrets
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.db import IntegrityError

from devices.models import Device, DeviceType
from .auth import require_api_key


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _parse_json_body(request):
    """Parse JSON body, kembalikan (data, error_response)."""
    try:
        data = json.loads(request.body)
        return data, None
    except (json.JSONDecodeError, ValueError):
        return None, JsonResponse(
            {'status': 'error', 'message': 'Body bukan JSON yang valid.'},
            status=400
        )


# ---------------------------------------------------------------------------
# POST /api/v1/devices/
# ---------------------------------------------------------------------------

@csrf_exempt
@require_api_key
@require_http_methods(["POST", "GET"])
def devices_endpoint(request):
    if request.method == 'GET':
        return _list_devices(request)
    return _create_device(request)


def _create_device(request):
    """
    Buat perangkat baru dari payload JSON.

    Field wajib : nama, jenis, merk, lokasi
    Field opsional: type, serial_number, firmware_version, ip_address,
                    status_operasi, keterangan, tahun_operasi

    Logika jenis  : case-insensitive match ke DeviceType.name.
                    Kalau tidak ditemukan → error 400.
    Logika duplikat: ip_address / serial_number sudah ada → error 409.
    """
    data, err = _parse_json_body(request)
    if err:
        return err

    # --- Validasi field wajib ---
    required = ['nama', 'jenis', 'merk', 'lokasi']
    missing = [f for f in required if not data.get(f, '').strip()]
    if missing:
        return JsonResponse(
            {'status': 'error', 'message': f'Field wajib tidak lengkap: {", ".join(missing)}'},
            status=400
        )

    # --- Resolusi DeviceType (case-insensitive) ---
    jenis_input = data['jenis'].strip()
    try:
        device_type = DeviceType.objects.get(name__iexact=jenis_input)
    except DeviceType.DoesNotExist:
        # Kirim daftar jenis yang tersedia agar n8n bisa log dengan jelas
        tersedia = list(DeviceType.objects.values_list('name', flat=True).order_by('name'))
        return JsonResponse(
            {
                'status': 'error',
                'message': f'Jenis perangkat "{jenis_input}" tidak ditemukan di database.',
                'jenis_tersedia': tersedia,
            },
            status=400
        )

    # --- Cek duplikat IP address ---
    ip_address = data.get('ip_address', '').strip() or None
    if ip_address and Device.objects.filter(ip_address=ip_address, is_deleted=False).exists():
        return JsonResponse(
            {
                'status': 'error',
                'message': f'IP address "{ip_address}" sudah terdaftar di sistem.',
                'field': 'ip_address',
            },
            status=409
        )

    # --- Cek duplikat serial number ---
    serial_number = data.get('serial_number', '').strip() or None
    if serial_number and Device.objects.filter(serial_number=serial_number, is_deleted=False).exists():
        return JsonResponse(
            {
                'status': 'error',
                'message': f'Serial number "{serial_number}" sudah terdaftar di sistem.',
                'field': 'serial_number',
            },
            status=409
        )

    # --- Validasi status_operasi ---
    status_operasi = data.get('status_operasi', 'operasi').strip().lower()
    if status_operasi not in ('operasi', 'tidak_operasi'):
        status_operasi = 'operasi'

    # --- Tahun operasi ---
    tahun_operasi = data.get('tahun_operasi', None)
    if tahun_operasi is not None:
        try:
            tahun_operasi = int(tahun_operasi)
        except (ValueError, TypeError):
            tahun_operasi = None

    # --- Buat Device ---
    try:
        device = Device.objects.create(
            nama=data['nama'].strip(),
            jenis=device_type,
            merk=data['merk'].strip(),
            type=data.get('type', '').strip() or None,
            serial_number=serial_number,
            firmware_version=data.get('firmware_version', '').strip() or None,
            ip_address=ip_address,
            lokasi=data['lokasi'].strip(),
            status_operasi=status_operasi,
            keterangan=data.get('keterangan', '').strip() or None,
            tahun_operasi=tahun_operasi,
            public_token=secrets.token_urlsafe(16),
            # created_by dibiarkan null karena request dari n8n (bukan user login)
        )
    except IntegrityError as e:
        # Tangkap constraint error lain (misal ip_address unique dari DB level)
        return JsonResponse(
            {'status': 'error', 'message': f'Gagal menyimpan data: {str(e)}'},
            status=409
        )

    return JsonResponse(
        {
            'status': 'ok',
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
    """
    GET /api/v1/devices/
    List perangkat aktif (is_deleted=False).
    Query params: jenis=Router, lokasi=GI+Tello
    """
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


# ---------------------------------------------------------------------------
# GET /api/v1/device-types/   — untuk n8n bisa cek jenis yang tersedia
# ---------------------------------------------------------------------------

@csrf_exempt
@require_api_key
@require_http_methods(["GET"])
def device_types_endpoint(request):
    types = list(DeviceType.objects.values('id', 'name').order_by('name'))
    return JsonResponse({'status': 'ok', 'count': len(types), 'device_types': types})


# ---------------------------------------------------------------------------
# GET /api/v1/ping/   — health check tanpa API key (untuk monitor uptime)
# ---------------------------------------------------------------------------

def ping(request):
    return JsonResponse({'status': 'ok', 'message': 'FASOP API aktif.'})
