from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import Maintenance, MaintenancePLC, MaintenanceRouter, MaintenanceRadio
from .forms import MaintenanceForm, MaintenancePLCForm, MaintenanceRouterForm, MaintenanceRadioForm
from devices.models import Device, DeviceType
from django.db.models import Q, Count
from django.db.models.functions import Trim
from django.http import HttpResponse
from io import BytesIO
import openpyxl
import json
from datetime import date as date_cls
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from datetime import date


# ─────────────────────────────────────────────────────────────────────
# MAPPING: nama jenis perangkat → (form class, template)
# Tambahkan jenis baru di sini tanpa ubah view!
# ─────────────────────────────────────────────────────────────────────
DEVICE_FORM_MAP = {
    'PLC':    (MaintenancePLCForm,    'maintenance/plc_form.html'),
    'ROUTER': (MaintenanceRouterForm, 'maintenance/router_form.html'),
    'SWITCH': (MaintenanceRouterForm, 'maintenance/switch_form.html'),
    'RADIO': (MaintenanceRadioForm, 'maintenance/radio_form.html'),
}

DEFAULT_TEMPLATE = 'maintenance/maintenance_form.html'


def _get_detail_form_config(device):
    """Return (FormClass, template) berdasarkan jenis perangkat."""
    if not device.jenis:
        return None, DEFAULT_TEMPLATE
    key = device.jenis.name.strip().upper()
    form_class, template = DEVICE_FORM_MAP.get(key, (None, DEFAULT_TEMPLATE))
    return form_class, template


# ─────────────────────────────────────────────────────────────────────
# LIST
# ─────────────────────────────────────────────────────────────────────
@login_required
def maintenance_list(request):
    status    = request.GET.get('status') or ''
    lokasi    = request.GET.get('lokasi') or ''
    jenis_id  = request.GET.get('jenis') or ''
    date_from = request.GET.get('date_from') or ''
    date_to   = request.GET.get('date_to') or ''

    maintenances = Maintenance.objects.select_related(
        'device', 'device__jenis'
    ).order_by('-date')

    if status:    maintenances = maintenances.filter(status=status)
    if lokasi:    maintenances = maintenances.filter(device__lokasi__iexact=lokasi)
    if jenis_id:  maintenances = maintenances.filter(device__jenis_id=jenis_id)
    if date_from: maintenances = maintenances.filter(date__gte=date_from)
    if date_to:   maintenances = maintenances.filter(date__lte=date_to)

    lokasi_list = (
        Maintenance.objects.select_related('device')
        .exclude(device__lokasi__isnull=True)
        .exclude(device__lokasi__exact='')
        .exclude(device__lokasi__iexact='none')
        .annotate(lokasi_clean=Trim('device__lokasi'))
        .values_list('lokasi_clean', flat=True)
        .distinct().order_by('lokasi_clean')
    )

    return render(request, 'maintenance/maintenance_list.html', {
        'maintenances':    maintenances,
        'lokasi_list':     lokasi_list,
        'selected_lokasi': lokasi,
        'selected_status': status,
        'jenis_list':      DeviceType.objects.all(),
        'selected_jenis':  jenis_id,
        'date_from':       date_from,
        'date_to':         date_to,
    })


# ─────────────────────────────────────────────────────────────────────
# CREATE  (otomatis pilih form berdasarkan jenis perangkat)
# ─────────────────────────────────────────────────────────────────────
@login_required
def maintenance_create(request, device_id):
    device = get_object_or_404(Device, id=device_id)
    detail_form_class, template = _get_detail_form_config(device)

    if request.method == 'POST':
        mform = MaintenanceForm(request.POST, request.FILES)
        dform = detail_form_class(request.POST) if detail_form_class else None

        if mform.is_valid() and (dform is None or dform.is_valid()):
            maintenance = mform.save(commit=False)
            maintenance.device = device
            maintenance.save()

            if dform:
                detail = dform.save(commit=False)
                detail.maintenance = maintenance
                detail.save()

            return redirect('maintenance_list')
    else:
        mform = MaintenanceForm()
        dform = detail_form_class() if detail_form_class else None

    return render(request, template, {
        'maintenance_form': mform,
        'detail_form':      dform,
        'device':           device,
    })


# ─────────────────────────────────────────────────────────────────────
# UPDATE STATUS
# ─────────────────────────────────────────────────────────────────────
@login_required
def maintenance_update_status(request, pk):
    maintenance = get_object_or_404(Maintenance, pk=pk)
    if request.method == 'POST':
        maintenance.status = request.POST.get('status')
        maintenance.save()
    return redirect('maintenance_list')


# ─────────────────────────────────────────────────────────────────────
# DETAIL
# ─────────────────────────────────────────────────────────────────────
@login_required
def maintenance_detail(request, pk):
    maintenance = get_object_or_404(Maintenance, pk=pk)
    device      = maintenance.device
    device_type = device.jenis.name.strip().upper() if device.jenis else ''

    plc_detail    = None
    router_detail = None
    radio_detail  = None

    if device_type == 'PLC':
        try:
            plc_detail = maintenance.maintenanceplc
        except MaintenancePLC.DoesNotExist:
            pass

    elif device_type in ('ROUTER', 'SWITCH'):
        try:
            router_detail = maintenance.maintenancerouter
        except MaintenanceRouter.DoesNotExist:
            pass

    elif device_type == 'RADIO':
        try:
            radio_detail = maintenance.maintenanceradio
        except MaintenanceRadio.DoesNotExist:
            pass

    # Checklist peralatan terpasang untuk template radio
    radio_checklist = []
    if radio_detail:
        radio_checklist = [
            ('ada_radio',        'Radio',         radio_detail.ada_radio),
            ('ada_battery',      'Battery',       radio_detail.ada_battery),
            ('ada_power_supply', 'Power Supply',  radio_detail.ada_power_supply),
        ]

    # Checklist fisik untuk template router
    router_checklist = []
    if router_detail and device_type == 'ROUTER':
        router_checklist = [
            ('Kondisi Fisik Unit',       router_detail.kondisi_fisik),
            ('Indikator LED Link/Port',  router_detail.led_link),
            ('Kondisi Kabel & Konektor', router_detail.kondisi_kabel),
        ]

    # Checklist fisik untuk template switch
    switch_checklist = []
    if router_detail and device_type == 'SWITCH':
        switch_checklist = [
            ('Kondisi Fisik Unit',       router_detail.kondisi_fisik),
            ('Indikator LED Link/Port',  router_detail.led_link),
            ('Kondisi Kabel & Konektor', router_detail.kondisi_kabel),
            ('Status Switching / VLAN',  router_detail.status_routing),
        ]

    return render(request, 'maintenance/maintenance_detail.html', {
        'maintenance':      maintenance,
        'device_type':      device_type,
        'plc_detail':       plc_detail,
        'router_detail':    router_detail,
        'radio_detail':     radio_detail,
        'radio_checklist':  radio_checklist,
        'router_checklist': router_checklist,
        'switch_checklist': switch_checklist,
    })




# ─────────────────────────────────────────────────────────────────────
# EDIT  (hanya status Open)
# ─────────────────────────────────────────────────────────────────────
@login_required
def maintenance_edit(request, pk):
    maintenance = get_object_or_404(Maintenance, pk=pk)
    device      = maintenance.device
    detail_form_class, template = _get_detail_form_config(device)

    # Ambil detail object yang sudah ada (jika ada)
    detail_instance = None
    if detail_form_class:
        try:
            if detail_form_class.__name__ == 'MaintenancePLCForm':
                detail_instance = maintenance.maintenanceplc
            elif detail_form_class.__name__ == 'MaintenanceRouterForm':
                detail_instance = maintenance.maintenancerouter
        except Exception:
            pass

    # Gunakan template edit yang sama dengan create
    edit_template = template  # reuse template yang sama

    if request.method == 'POST':
        mform = MaintenanceForm(request.POST, request.FILES, instance=maintenance)
        dform = detail_form_class(request.POST, instance=detail_instance) if detail_form_class else None

        if mform.is_valid() and (dform is None or dform.is_valid()):
            mform.save()
            if dform:
                detail = dform.save(commit=False)
                detail.maintenance = maintenance
                detail.save()
            return redirect('maintenance_view', pk=pk)
    else:
        mform = MaintenanceForm(instance=maintenance)
        dform = detail_form_class(instance=detail_instance) if detail_form_class else None

    return render(request, edit_template, {
        'maintenance_form': mform,
        'detail_form':      dform,
        'device':           device,
        'is_edit':          True,
        'maintenance':      maintenance,
    })

# ─────────────────────────────────────────────────────────────────────
# DELETE
# ─────────────────────────────────────────────────────────────────────
@login_required
def maintenance_delete(request, pk):
    maintenance = get_object_or_404(Maintenance, pk=pk)
    maintenance.delete()
    return redirect('maintenance_list')


# ─────────────────────────────────────────────────────────────────────
# LAPORAN BULANAN
# ─────────────────────────────────────────────────────────────────────
@login_required
def maintenance_report(request):
    today          = date.today()
    selected_month = int(request.GET.get('month') or today.month)
    selected_year  = int(request.GET.get('year')  or today.year)

    maintenances = (
        Maintenance.objects
        .filter(date__year=selected_year, date__month=selected_month)
        .select_related('device', 'device__jenis', 'technician')
        .order_by('date')
    )

    total     = maintenances.count()
    done      = maintenances.filter(status='Done').count()
    open_count = maintenances.filter(status='Open').count()
    preventive = maintenances.filter(maintenance_type='Preventive').count()

    by_type_qs = (
        maintenances.values('device__jenis__name')
        .annotate(total=Count('id'))
        .order_by('device__jenis__name')
    )
    by_type = []
    for row in by_type_qs:
        jenis_name = row['device__jenis__name']
        done_c = maintenances.filter(device__jenis__name=jenis_name, status='Done').count()
        open_c = maintenances.filter(device__jenis__name=jenis_name, status='Open').count()
        by_type.append({**row, 'done': done_c, 'open': open_c})

    month_names = [
        'Januari','Februari','Maret','April','Mei','Juni',
        'Juli','Agustus','September','Oktober','November','Desember'
    ]
    month_choices = [{'value': i+1, 'label': n} for i, n in enumerate(month_names)]
    first_year = (
        Maintenance.objects.order_by('date').first().date.year
        if Maintenance.objects.exists() else today.year
    )
    year_choices = list(range(first_year, today.year + 1))

    return render(request, 'maintenance/maintenance_report.html', {
        'maintenances':    maintenances,
        'summary':         {'total': total, 'done': done, 'open': open_count, 'preventive': preventive},
        'by_type':         by_type,
        'selected_month':  selected_month,
        'selected_year':   selected_year,
        'month_choices':   month_choices,
        'year_choices':    year_choices,
        'period_label':    f"{month_names[selected_month-1]} {selected_year}",
    })


# ─────────────────────────────────────────────────────────────────────
# EXPORT EXCEL
# ─────────────────────────────────────────────────────────────────────
@login_required
def export_maintenance_excel(request):
    status    = request.GET.get('status') or ''
    lokasi    = request.GET.get('lokasi') or ''
    jenis_id  = request.GET.get('jenis') or ''
    date_from = request.GET.get('date_from') or ''
    date_to   = request.GET.get('date_to') or ''
    year      = request.GET.get('year') or ''
    month     = request.GET.get('month') or ''

    qs = Maintenance.objects.select_related('device','device__jenis','technician').order_by('-date')

    if status:    qs = qs.filter(status=status)
    if lokasi:    qs = qs.filter(device__lokasi__iexact=lokasi)
    if jenis_id:  qs = qs.filter(device__jenis_id=jenis_id)
    if date_from: qs = qs.filter(date__gte=date_from)
    if date_to:   qs = qs.filter(date__lte=date_to)
    if year and month:
        qs = qs.filter(date__year=int(year), date__month=int(month))

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Data Pemeliharaan"

    hdr_fill   = PatternFill("solid", fgColor="0F172A")
    hdr_font   = Font(bold=True, color="FFFFFF", size=11)
    hdr_align  = Alignment(horizontal="center", vertical="center", wrap_text=True)
    c_align    = Alignment(horizontal="center", vertical="center")
    thin       = Border(left=Side(style='thin'), right=Side(style='thin'),
                        top=Side(style='thin'),  bottom=Side(style='thin'))
    done_fill  = PatternFill("solid", fgColor="D1FAE5")
    open_fill  = PatternFill("solid", fgColor="FEF3C7")
    alt_fill   = PatternFill("solid", fgColor="F8FAFC")

    ws.merge_cells('A1:H1')
    ws['A1'].value = "DATA PEMELIHARAAN PERALATAN FASOP UP2B"
    ws['A1'].font  = Font(bold=True, size=13)
    ws['A1'].alignment = Alignment(horizontal="center", vertical="center")
    ws['A1'].fill  = PatternFill("solid", fgColor="EFF6FF")
    ws.row_dimensions[1].height = 28

    ws.merge_cells('A2:H2')
    ws['A2'].value = f"Dicetak: {date.today().strftime('%d %B %Y')}"
    ws['A2'].alignment = Alignment(horizontal="center")
    ws['A2'].font  = Font(size=10, italic=True, color="64748B")
    ws.row_dimensions[3].height = 6

    headers    = ['No','Tanggal','Perangkat','Lokasi','Jenis','Pelaksana','Deskripsi','Status']
    col_widths = [5, 14, 25, 20, 18, 18, 35, 12]

    for ci, (h, w) in enumerate(zip(headers, col_widths), 1):
        cell = ws.cell(row=4, column=ci, value=h)
        cell.font = hdr_font; cell.fill = hdr_fill
        cell.alignment = hdr_align; cell.border = thin
        ws.column_dimensions[get_column_letter(ci)].width = w
    ws.row_dimensions[4].height = 22

    for ri, m in enumerate(qs, 1):
        wr = ri + 4
        row_data = [ri, m.date.strftime('%d/%m/%Y'), str(m.device), m.device.lokasi,
                    m.maintenance_type, str(m.technician) if m.technician else '-',
                    m.description or '-', m.status]
        for ci, val in enumerate(row_data, 1):
            cell = ws.cell(row=wr, column=ci, value=val)
            cell.border = thin
            cell.alignment = c_align if ci in [1,2,5,8] else Alignment(vertical="center", wrap_text=True)
            if ci == 8:
                cell.fill = done_fill if val == 'Done' else open_fill
                cell.font = Font(bold=True, color="065F46" if val == 'Done' else "92400E")
            elif ri % 2 == 0:
                cell.fill = alt_fill
        ws.row_dimensions[wr].height = 18

    ws.freeze_panes = 'A5'
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename="pemeliharaan_fasop.xlsx"'
    wb.save(response)
    return response


# ─────────────────────────────────────────────────────────────────────
# EXPORT PDF LAPORAN PEMELIHARAAN
# ─────────────────────────────────────────────────────────────────────
@login_required
def export_maintenance_pdf(request, pk):
    from .pdf_export import build_pdf

    maintenance = get_object_or_404(Maintenance, pk=pk)
    device      = maintenance.device
    device_kind = device.jenis.name.strip().upper() if device.jenis else 'GENERIC'

    # ── Ambil detail sesuai jenis ──────────────────────────────────
    router_detail = None
    plc_detail    = None

    if device_kind in ('ROUTER', 'SWITCH'):
        try:
            router_detail = maintenance.maintenancerouter
        except MaintenanceRouter.DoesNotExist:
            pass
    elif device_kind == 'PLC':
        try:
            plc_detail = maintenance.maintenanceplc
        except MaintenancePLC.DoesNotExist:
            pass

    # SFP JSON
    sfp_ports = []
    if router_detail and router_detail.sfp_port_data:
        try:
            sfp_ports = json.loads(router_detail.sfp_port_data)
        except Exception:
            pass

    # ── Susun dict data ────────────────────────────────────────────
    def _g(obj, attr, default=None):
        """getattr with empty-string fallback."""
        val = getattr(obj, attr, default)
        return val if val not in (None, '') else default

    data = {
        'print_date':  date_cls.today().strftime('%d %B %Y'),
        'device_kind': device_kind,

        'info': {
            'device_name':      device.nama,
            'device_type':      str(device.jenis) if device.jenis else '-',
            'lokasi':           _g(device, 'lokasi', '-'),
            'ip_address':       _g(device, 'ip_address', '-'),
            'serial_number':    _g(device, 'serial_number', '-'),
            'brand':            _g(device, 'merk', '-'),
            'date':             maintenance.date.strftime('%d %B %Y'),
            'maintenance_type': maintenance.maintenance_type,
            'technician':       str(maintenance.technician) if maintenance.technician else '-',
            'status':           maintenance.status,
            'description':      maintenance.description or '',
        },

        # Router / Switch fields
        'fisik': {
            'kondisi_fisik': _g(router_detail, 'kondisi_fisik', ''),
            'led_link':      _g(router_detail, 'led_link', ''),
            'kondisi_kabel': _g(router_detail, 'kondisi_kabel', ''),
        } if router_detail else {},

        'pengukuran': {
            'tegangan_input': _g(router_detail, 'tegangan_input'),
            'suhu_perangkat': _g(router_detail, 'suhu_perangkat'),
            'cpu_load':       _g(router_detail, 'cpu_load'),
            'memory_usage':   _g(router_detail, 'memory_usage'),
        } if router_detail else {},

        'port': {
            'jumlah_port_aktif': _g(router_detail, 'jumlah_port_aktif'),
            'jumlah_port_total': _g(router_detail, 'jumlah_port_total'),
            'status_routing':    _g(router_detail, 'status_routing', ''),
            'detail_port':       _g(router_detail, 'detail_port', ''),
        } if router_detail else {},

        'sfp_ports':        sfp_ports,
        'catatan_tambahan': (_g(router_detail, 'catatan_tambahan', '') if router_detail else ''),

        # PLC fields
        'plc': {
            'akses_plc':          _g(plc_detail, 'akses_plc', ''),
            'remote_akses_plc':   _g(plc_detail, 'remote_akses_plc', ''),
            'time_sync':          _g(plc_detail, 'time_sync', ''),
            'wave_trap':          _g(plc_detail, 'wave_trap', ''),
            'imu':                _g(plc_detail, 'imu', ''),
            'kabel_coaxial':      _g(plc_detail, 'kabel_coaxial', ''),
            'transmission_line':  _g(plc_detail, 'transmission_line'),
            'rx_pilot_level':     _g(plc_detail, 'rx_pilot_level'),
            'freq_tx':            _g(plc_detail, 'freq_tx'),
            'bandwidth_tx':       _g(plc_detail, 'bandwidth_tx'),
            'freq_rx':            _g(plc_detail, 'freq_rx'),
            'bandwidth_rx':       _g(plc_detail, 'bandwidth_rx'),
        } if plc_detail else {},
    }

    # ── Generate & stream ──────────────────────────────────────────
    buffer = BytesIO()
    build_pdf(data, buffer)
    buffer.seek(0)

    filename = (f"laporan_{device.nama}_{maintenance.date}.pdf"
                .replace(' ', '_').replace('/', '-'))
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response
