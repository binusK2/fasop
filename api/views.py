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