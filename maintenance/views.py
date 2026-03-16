from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import Maintenance, MaintenancePLC, MaintenanceRouter, MaintenanceRadio, MaintenanceVoIP, MaintenanceMux, MaintenanceRectifier
from .forms import MaintenanceForm, MaintenancePLCForm, MaintenanceRouterForm, MaintenanceRadioForm, MaintenanceVoIPForm, MaintenanceMuxForm, MaintenanceRectifierForm
from devices.models import Device, DeviceType
from django.db.models import Q, Count
from django.db.models.functions import Trim
from django.http import HttpResponse
from io import BytesIO
import openpyxl
import json
from datetime import date as date_cls
from django.utils import timezone as dj_timezone
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
    'VOIP':        (MaintenanceVoIPForm,  'maintenance/voip_form.html'),
    'MULTIPLEXER':  (MaintenanceMuxForm,        'maintenance/mux_form.html'),
    'RECTIFIER':    (MaintenanceRectifierForm,   'maintenance/rectifier_form.html'),
    'CATU DAYA':    (MaintenanceRectifierForm,   'maintenance/rectifier_form.html'),
    'CATUDAYA':     (MaintenanceRectifierForm,   'maintenance/rectifier_form.html'),
    'RECTIFIER & BATTERY': (MaintenanceRectifierForm, 'maintenance/rectifier_form.html'),
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
            maintenance.status = 'Open'  # selalu Open saat baru dibuat
            # Simpan nama pelaksana manual (JSON array dari tag-input)
            names_raw = request.POST.get('pelaksana_names', '[]')
            try:
                maintenance.pelaksana_names = json.loads(names_raw)
            except (json.JSONDecodeError, ValueError):
                maintenance.pelaksana_names = []
            maintenance.save()

            if dform:
                detail = dform.save(commit=False)
                detail.maintenance = maintenance
                detail.save()

            return redirect('maintenance_list')
    else:
        mform = MaintenanceForm()
        dform = detail_form_class() if detail_form_class else None

    slot_fields = []
    if dform and dform.__class__.__name__ == 'MaintenanceMuxForm':
        for letter in 'ABCDEFGH':
            l = letter.lower()
            slot_fields.append((letter, dform['slot_' + l + '_modul'], dform['slot_' + l + '_isian']))

    return render(request, template, {
        'maintenance_form': mform,
        'detail_form':      dform,
        'device':           device,
        'slot_fields':      slot_fields,
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
    voip_detail   = None
    mux_detail    = None
    rect_detail   = None

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

    elif device_type == 'VOIP':
        try:
            voip_detail = maintenance.maintenancevoip
        except MaintenanceVoIP.DoesNotExist:
            pass

    elif device_type == 'MULTIPLEXER':
        try:
            mux_detail = maintenance.maintenancemux
        except MaintenanceMux.DoesNotExist:
            pass

    elif device_type in ('RECTIFIER', 'CATU DAYA', 'CATUDAYA', 'RECTIFIER & BATTERY'):
        try:
            rect_detail = maintenance.maintenancerectifier
        except MaintenanceRectifier.DoesNotExist:
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



    # Context untuk Rectifier detail
    rect_list = []
    bat_list  = []
    if rect_detail:
        d = rect_detail
        # rect_list: (rn, merk, tipe, kondisi, kapasitas, v_rect, v_bat, teg_pos, teg_neg, v_drop, a_rect, a_bat, a_load)
        for n in [1, 2]:
            rect_list.append((
                n,
                getattr(d, f'rect{n}_merk', ''),
                getattr(d, f'rect{n}_tipe', ''),
                getattr(d, f'rect{n}_kondisi', ''),
                getattr(d, f'rect{n}_kapasitas', ''),
                getattr(d, f'rect{n}_v_rectifier', None),
                getattr(d, f'rect{n}_v_battery', None),
                getattr(d, f'rect{n}_teg_pos_ground', None),
                getattr(d, f'rect{n}_teg_neg_ground', None),
                getattr(d, f'rect{n}_v_dropper', None),
                getattr(d, f'rect{n}_a_rectifier', None),
                getattr(d, f'rect{n}_a_battery', None),
                getattr(d, f'rect{n}_a_load', None),
            ))
        # bat_list: (bn, merk, tipe, kondisi, kapasitas, jumlah, kabel, mur, sel_rak, air, v_total, v_load, cells)
        for n in [1, 2]:
            bat_list.append((
                n,
                getattr(d, f'bat{n}_merk', ''),
                getattr(d, f'bat{n}_tipe', ''),
                getattr(d, f'bat{n}_kondisi', ''),
                getattr(d, f'bat{n}_kapasitas', ''),
                getattr(d, f'bat{n}_jumlah', None),
                getattr(d, f'bat{n}_kondisi_kabel', ''),
                getattr(d, f'bat{n}_kondisi_mur_baut', ''),
                getattr(d, f'bat{n}_kondisi_sel_rak', ''),
                getattr(d, f'bat{n}_air_battery', None),
                getattr(d, f'bat{n}_v_total', None),
                getattr(d, f'bat{n}_v_load', None),
                getattr(d, f'bat{n}_cells', []),
            ))

    # Context tambahan untuk MUX detail
    mux_slots = []
    mux_psu_list = []
    hs_list = []
    if mux_detail:
        for letter in 'ABCDEFGH':
            l = letter.lower()
            mux_slots.append((
                letter,
                getattr(mux_detail, f'slot_{l}_modul', ''),
                getattr(mux_detail, f'slot_{l}_isian', ''),
            ))
        mux_psu_list = [
            ('PSU 1', mux_detail.psu1_status, mux_detail.psu1_temp1, mux_detail.psu1_temp2, mux_detail.psu1_temp3),
            ('PSU 2', mux_detail.psu2_status, mux_detail.psu2_temp1, mux_detail.psu2_temp2, mux_detail.psu2_temp3),
            ('FAN',   mux_detail.fan_status,  None, None, None),
        ]
        hs_list = [('1', 'hs1'), ('2', 'hs2')]

    # Checklist untuk Mux (PSU & FAN status)
    mux_checklist = []
    if mux_detail:
        mux_checklist = [
            ('PSU 1', mux_detail.psu1_status),
            ('PSU 2', mux_detail.psu2_status),
            ('FAN',   mux_detail.fan_status),
        ]

    # Checklist untuk VoIP
    voip_checklist = []
    if voip_detail:
        voip_checklist = [
            ('Kondisi Fisik Perangkat', voip_detail.kondisi_fisik),
            ('NTP Server',             voip_detail.ntp_server),
            ('Web Config',             voip_detail.webconfig),
            ('Status Power Supply',    voip_detail.ps_status),
        ]

    return render(request, 'maintenance/maintenance_detail.html', {
        'maintenance':      maintenance,
        'device_type':      device_type,
        'plc_detail':       plc_detail,
        'router_detail':    router_detail,
        'radio_detail':     radio_detail,
        'voip_detail':      voip_detail,
        'voip_checklist':   voip_checklist,
        'mux_detail':       mux_detail,
        'mux_checklist':    mux_checklist,
        'mux_slots':        mux_slots,
        'mux_psu_list':     mux_psu_list,
        'hs_list':          hs_list,
        'rect_detail':      rect_detail,
        'rect_list':        rect_list,
        'bat_list':         bat_list,
        'rect_v_list':      [('Rectifier', rect_detail.rect1_v_rectifier if rect_detail else None, 'V'), ('Battery', rect_detail.rect1_v_battery if rect_detail else None, 'V'), ('Teg(+) GND', rect_detail.rect1_teg_pos_ground if rect_detail else None, 'V'), ('Teg(-) GND', rect_detail.rect1_teg_neg_ground if rect_detail else None, 'V'), ('Dropper', rect_detail.rect1_v_dropper if rect_detail else None, 'V')] if rect_detail else [],
        'rect_a_list':      [('Rectifier', rect_detail.rect1_a_rectifier if rect_detail else None), ('Battery', rect_detail.rect1_a_battery if rect_detail else None), ('Load', rect_detail.rect1_a_load if rect_detail else None)] if rect_detail else [],
        'bat_kondisi_list': [('Kabel Battery', rect_detail.bat1_kondisi_kabel if rect_detail else ''), ('Mur & Baut', rect_detail.bat1_kondisi_mur_baut if rect_detail else ''), ('Sel & Rak', rect_detail.bat1_kondisi_sel_rak if rect_detail else '')] if rect_detail else [],
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
            elif detail_form_class.__name__ == 'MaintenanceRadioForm':
                detail_instance = maintenance.maintenanceradio
            elif detail_form_class.__name__ == 'MaintenanceVoIPForm':
                detail_instance = maintenance.maintenancevoip
            elif detail_form_class.__name__ == 'MaintenanceMuxForm':
                detail_instance = maintenance.maintenancemux
            elif detail_form_class.__name__ == 'MaintenanceRectifierForm':
                detail_instance = maintenance.maintenancerectifier
        except Exception:
            pass

    # Gunakan template edit yang sama dengan create
    edit_template = template  # reuse template yang sama

    if request.method == 'POST':
        mform = MaintenanceForm(request.POST, request.FILES, instance=maintenance)
        dform = detail_form_class(request.POST, instance=detail_instance) if detail_form_class else None

        if mform.is_valid() and (dform is None or dform.is_valid()):
            m = mform.save(commit=False)
            names_raw = request.POST.get('pelaksana_names', '[]')
            try:
                m.pelaksana_names = json.loads(names_raw)
            except (json.JSONDecodeError, ValueError):
                m.pelaksana_names = []
            m.save()
            if dform:
                detail = dform.save(commit=False)
                detail.maintenance = maintenance
                detail.save()
            return redirect('maintenance_view', pk=pk)
    else:
        mform = MaintenanceForm(instance=maintenance)
        dform = detail_form_class(instance=detail_instance) if detail_form_class else None

    slot_fields_edit = []
    if dform and dform.__class__.__name__ == 'MaintenanceMuxForm':
        for letter in 'ABCDEFGH':
            l = letter.lower()
            slot_fields_edit.append((letter, dform['slot_' + l + '_modul'], dform['slot_' + l + '_isian']))

    return render(request, edit_template, {
        'maintenance_form': mform,
        'detail_form':      dform,
        'device':           device,
        'is_edit':          True,
        'maintenance':      maintenance,
        'slot_fields':      slot_fields_edit,
        'pelaksana_names_json': json.dumps(maintenance.pelaksana_names or []),
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
        .select_related('device', 'device__jenis', 'signed_by')
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

    qs = Maintenance.objects.select_related('device','device__jenis','signed_by').prefetch_related('technicians').order_by('-date')

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
                    m.maintenance_type, ', '.join(t.get_full_name() or t.username for t in m.technicians.all()) or '-',
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
    router_detail = plc_detail = radio_detail = None
    voip_detail = mux_detail = rect_detail = None

    def _try(fn):
        try: return fn()
        except Exception: return None

    if device_kind in ('ROUTER', 'SWITCH'):
        router_detail = _try(lambda: maintenance.maintenancerouter)
    elif device_kind == 'PLC':
        plc_detail = _try(lambda: maintenance.maintenanceplc)
    elif device_kind == 'RADIO':
        radio_detail = _try(lambda: maintenance.maintenanceradio)
    elif device_kind == 'VOIP':
        voip_detail = _try(lambda: maintenance.maintenancevoip)
    elif device_kind == 'MULTIPLEXER':
        mux_detail = _try(lambda: maintenance.maintenancemux)
    elif device_kind in ('RECTIFIER', 'CATU DAYA', 'CATUDAYA', 'RECTIFIER & BATTERY'):
        rect_detail = _try(lambda: maintenance.maintenancerectifier)

    # SFP JSON
    sfp_ports = []
    if router_detail and router_detail.sfp_port_data:
        try: sfp_ports = json.loads(router_detail.sfp_port_data)
        except Exception: pass

    # ── Susun dict data ────────────────────────────────────────────
    def _g(obj, attr, default=None):
        val = getattr(obj, attr, default)
        return val if val not in (None, '') else default

    # Signature dari asisten manager
    sigs = {}
    if maintenance.signed_by:
        try:
            sig_path = maintenance.signed_by.profile.signature.path
            if sig_path:
                sigs['asisten_manager'] = sig_path
        except Exception:
            pass
    # Signature pelaksana (technician pertama yang punya signature)
    for tech in maintenance.technicians.all():
        try:
            sp = tech.profile.signature.path
            if sp:
                sigs['operator'] = sp
                break
        except Exception:
            pass

    # Nama pelaksana: prioritaskan pelaksana_names (input manual), fallback ke User M2M
    if maintenance.pelaksana_names:
        techs_str = ', '.join(n for n in maintenance.pelaksana_names if n)
    else:
        techs_str = ', '.join(
            t.get_full_name() or t.username for t in maintenance.technicians.all()
        ) or '-'

    data = {
        'print_date':  dj_timezone.localtime(dj_timezone.now()).strftime('%d %B %Y  %H:%M'),
        'print_by':    request.user.get_full_name() or request.user.username,
        'device_kind': device_kind,
        'signatures':  sigs,

        'info': {
            'device_name':      device.nama,
            'device_type':      str(device.jenis) if device.jenis else '-',
            'lokasi':           _g(device, 'lokasi', '-'),
            'ip_address':       _g(device, 'ip_address', '-'),
            'serial_number':    _g(device, 'serial_number', '-'),
            'merk':            _g(device, 'merk', '-'),
            'type':             _g(device, 'type', '-'),
            'date':             dj_timezone.localtime(maintenance.date).strftime('%d %B %Y  %H:%M'),
            'maintenance_type': maintenance.maintenance_type,
            'technician':       techs_str,
            'status':           maintenance.status,
            'description':      maintenance.description or '',
            'catatan_am':       maintenance.catatan_am or '',
            'signed_by':        maintenance.signed_by.profile.get_display_name() if maintenance.signed_by and hasattr(maintenance.signed_by, 'profile') else (maintenance.signed_by.get_full_name() or maintenance.signed_by.username if maintenance.signed_by else ''),
        },

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

        'plc': {
            'akses_plc':         _g(plc_detail, 'akses_plc', ''),
            'remote_akses_plc':  _g(plc_detail, 'remote_akses_plc', ''),
            'time_sync':         _g(plc_detail, 'time_sync', ''),
            'wave_trap':         _g(plc_detail, 'wave_trap', ''),
            'imu':               _g(plc_detail, 'imu', ''),
            'kabel_coaxial':     _g(plc_detail, 'kabel_coaxial', ''),
            'transmission_line': _g(plc_detail, 'transmission_line'),
            'rx_pilot_level':    _g(plc_detail, 'rx_pilot_level'),
            'freq_tx':           _g(plc_detail, 'freq_tx'),
            'bandwidth_tx':      _g(plc_detail, 'bandwidth_tx'),
            'freq_rx':           _g(plc_detail, 'freq_rx'),
            'bandwidth_rx':      _g(plc_detail, 'bandwidth_rx'),
        } if plc_detail else {},

        'radio': {
            'suhu_ruangan':     _g(radio_detail, 'suhu_ruangan'),
            'kebersihan':       _g(radio_detail, 'kebersihan', ''),
            'lampu_penerangan': _g(radio_detail, 'lampu_penerangan', ''),
            'ada_radio':        _g(radio_detail, 'ada_radio', ''),
            'ada_battery':      _g(radio_detail, 'ada_battery', ''),
            'merk_battery':     _g(radio_detail, 'merk_battery', ''),
            'ada_power_supply': _g(radio_detail, 'ada_power_supply', ''),
            'merk_power_supply':_g(radio_detail, 'merk_power_supply', ''),
            'jenis_antena':     _g(radio_detail, 'jenis_antena', ''),
            'swr':              _g(radio_detail, 'swr', ''),
            'power_tx':         _g(radio_detail, 'power_tx'),
            'tegangan_battery': _g(radio_detail, 'tegangan_battery'),
            'tegangan_psu':     _g(radio_detail, 'tegangan_psu'),
            'frekuensi_tx':     _g(radio_detail, 'frekuensi_tx'),
            'frekuensi_rx':     _g(radio_detail, 'frekuensi_rx'),
            'catatan':          _g(radio_detail, 'catatan', ''),
        } if radio_detail else {},

        'voip': {
            'ip_address':        _g(voip_detail, 'ip_address', ''),
            'extension_number':  _g(voip_detail, 'extension_number', ''),
            'sip_server_1':      _g(voip_detail, 'sip_server_1', ''),
            'sip_server_2':      _g(voip_detail, 'sip_server_2', ''),
            'suhu_ruangan':      _g(voip_detail, 'suhu_ruangan'),
            'kondisi_fisik':     _g(voip_detail, 'kondisi_fisik', ''),
            'ntp_server':        _g(voip_detail, 'ntp_server', ''),
            'webconfig':         _g(voip_detail, 'webconfig', ''),
            'ps_merk':           _g(voip_detail, 'ps_merk', ''),
            'ps_tegangan_input': _g(voip_detail, 'ps_tegangan_input'),
            'ps_status':         _g(voip_detail, 'ps_status', ''),
            'catatan':           _g(voip_detail, 'catatan', ''),
        } if voip_detail else {},

        'mux': {
            'brand':         _g(mux_detail, 'brand', ''),
            'firmware':      _g(mux_detail, 'firmware', ''),
            'sync_source_1': _g(mux_detail, 'sync_source_1', ''),
            'sync_source_2': _g(mux_detail, 'sync_source_2', ''),
            'suhu_ruangan':  _g(mux_detail, 'suhu_ruangan'),
            'kebersihan':    _g(mux_detail, 'kebersihan', ''),
            'hs1_merk':      _g(mux_detail, 'hs1_merk', ''),
            'hs1_tx_bias':   _g(mux_detail, 'hs1_tx_bias'),
            'hs1_jarak':     _g(mux_detail, 'hs1_jarak'),
            'hs1_tx':        _g(mux_detail, 'hs1_tx'),
            'hs1_lambda':    _g(mux_detail, 'hs1_lambda'),
            'hs1_suhu':      _g(mux_detail, 'hs1_suhu'),
            'hs1_rx':        _g(mux_detail, 'hs1_rx'),
            'hs1_bandwidth': _g(mux_detail, 'hs1_bandwidth', ''),
            'hs2_merk':      _g(mux_detail, 'hs2_merk', ''),
            'hs2_tx_bias':   _g(mux_detail, 'hs2_tx_bias'),
            'hs2_jarak':     _g(mux_detail, 'hs2_jarak'),
            'hs2_tx':        _g(mux_detail, 'hs2_tx'),
            'hs2_lambda':    _g(mux_detail, 'hs2_lambda'),
            'hs2_suhu':      _g(mux_detail, 'hs2_suhu'),
            'hs2_rx':        _g(mux_detail, 'hs2_rx'),
            'hs2_bandwidth': _g(mux_detail, 'hs2_bandwidth', ''),
            'psu1_status':   _g(mux_detail, 'psu1_status', ''),
            'psu1_temp1':    _g(mux_detail, 'psu1_temp1'),
            'psu1_temp2':    _g(mux_detail, 'psu1_temp2'),
            'psu1_temp3':    _g(mux_detail, 'psu1_temp3'),
            'psu2_status':   _g(mux_detail, 'psu2_status', ''),
            'psu2_temp1':    _g(mux_detail, 'psu2_temp1'),
            'psu2_temp2':    _g(mux_detail, 'psu2_temp2'),
            'psu2_temp3':    _g(mux_detail, 'psu2_temp3'),
            'fan_status':    _g(mux_detail, 'fan_status', ''),
            'catatan':       _g(mux_detail, 'catatan', ''),
            **{f'slot_{l.lower()}_modul': _g(mux_detail, f'slot_{l.lower()}_modul', '')
               for l in 'ABCDEFGH'},
            **{f'slot_{l.lower()}_isian': _g(mux_detail, f'slot_{l.lower()}_isian', '')
               for l in 'ABCDEFGH'},
        } if mux_detail else {},

        'rectifier': {
            'suhu_ruangan':        _g(rect_detail, 'suhu_ruangan'),
            'exhaust_fan':         _g(rect_detail, 'exhaust_fan', ''),
            'kebersihan':          _g(rect_detail, 'kebersihan', ''),
            'lampu_penerangan':    _g(rect_detail, 'lampu_penerangan', ''),
            'rect1_merk':          _g(rect_detail, 'rect1_merk', ''),
            'rect1_tipe':          _g(rect_detail, 'rect1_tipe', ''),
            'rect1_kondisi':       _g(rect_detail, 'rect1_kondisi', ''),
            'rect1_kapasitas':     _g(rect_detail, 'rect1_kapasitas', ''),
            'rect1_v_rectifier':   _g(rect_detail, 'rect1_v_rectifier'),
            'rect1_v_battery':     _g(rect_detail, 'rect1_v_battery'),
            'rect1_teg_pos_ground':_g(rect_detail, 'rect1_teg_pos_ground'),
            'rect1_teg_neg_ground':_g(rect_detail, 'rect1_teg_neg_ground'),
            'rect1_v_dropper':     _g(rect_detail, 'rect1_v_dropper'),
            'rect1_a_rectifier':   _g(rect_detail, 'rect1_a_rectifier'),
            'rect1_a_battery':     _g(rect_detail, 'rect1_a_battery'),
            'rect1_a_load':        _g(rect_detail, 'rect1_a_load'),
            'bat1_merk':           _g(rect_detail, 'bat1_merk', ''),
            'bat1_tipe':           _g(rect_detail, 'bat1_tipe', ''),
            'bat1_kondisi':        _g(rect_detail, 'bat1_kondisi', ''),
            'bat1_kapasitas':      _g(rect_detail, 'bat1_kapasitas', ''),
            'bat1_jumlah':         _g(rect_detail, 'bat1_jumlah'),
            'bat1_kondisi_kabel':  _g(rect_detail, 'bat1_kondisi_kabel', ''),
            'bat1_kondisi_mur_baut':_g(rect_detail,'bat1_kondisi_mur_baut',''),
            'bat1_kondisi_sel_rak': _g(rect_detail,'bat1_kondisi_sel_rak', ''),
            'bat1_air_battery':    _g(rect_detail, 'bat1_air_battery'),
            'bat1_v_total':        _g(rect_detail, 'bat1_v_total'),
            'bat1_v_load':         _g(rect_detail, 'bat1_v_load'),
            'bat1_cells':          _g(rect_detail, 'bat1_cells', []),
            'catatan':             _g(rect_detail, 'catatan', ''),
        } if rect_detail else {},
    }

    # ── Generate & stream ──────────────────────────────────────────
    buffer = BytesIO()
    build_pdf(data, buffer)
    buffer.seek(0)

    clean_date = dj_timezone.localtime(maintenance.date).strftime('%d-%m-%Y_%H.%M')
    filename = f"LAPORAN_PEMELIHARAAN_{device.nama}_{clean_date}.pdf".replace(' ', '_')
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


# ─────────────────────────────────────────────────────────────────────
# TANDA TANGAN (Asisten Manager)
# ─────────────────────────────────────────────────────────────────────
@login_required
def maintenance_sign(request, pk):
    """Asisten Manager menandatangani laporan pemeliharaan."""
    from django.utils import timezone
    maintenance = get_object_or_404(Maintenance, pk=pk)

    # Hanya asisten manager boleh sign
    try:
        is_am = request.user.profile.is_asisten_manager
    except Exception:
        is_am = False

    if not is_am:
        from django.contrib import messages
        messages.error(request, 'Hanya Asisten Manager yang dapat menandatangani laporan.')
        return redirect('maintenance_view', pk=pk)

    if request.method == 'POST':
        maintenance.signed_by = request.user
        maintenance.signed_at = timezone.now()
        maintenance.catatan_am = request.POST.get('catatan_am', '').strip()
        maintenance.save(update_fields=['signed_by', 'signed_at', 'catatan_am'])
        from django.contrib import messages
        messages.success(request, 'Laporan berhasil ditandatangani.')

    return redirect('maintenance_view', pk=pk)


@login_required
def maintenance_catatan_am_edit(request, pk):
    """Asisten Manager mengedit / menambah catatan setelah TTD."""
    maintenance = get_object_or_404(Maintenance, pk=pk)

    try:
        is_am = request.user.profile.is_asisten_manager
    except Exception:
        is_am = False

    if not is_am:
        from django.contrib import messages
        messages.error(request, 'Hanya Asisten Manager yang dapat mengubah catatan.')
        return redirect('maintenance_view', pk=pk)

    if request.method == 'POST':
        maintenance.catatan_am = request.POST.get('catatan_am', '').strip()
        maintenance.save(update_fields=['catatan_am'])
        from django.contrib import messages
        messages.success(request, 'Catatan berhasil diperbarui.')

    return redirect('maintenance_view', pk=pk)


# ─────────────────────────────────────────────────────────────────────
# PROFILE — upload tanda tangan
# ─────────────────────────────────────────────────────────────────────
@login_required
def profile_view(request):
    from devices.models import UserProfile
    from django.contrib import messages
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    if request.method == 'POST':
        if 'signature' in request.FILES:
            profile.signature = request.FILES['signature']
            profile.save()
            messages.success(request, 'Tanda tangan berhasil disimpan.')
        elif 'save_display_name' in request.POST:
            profile.display_name = request.POST.get('display_name', '').strip()
            profile.save(update_fields=['display_name'])
            messages.success(request, 'Nama tampilan berhasil disimpan.')
        return redirect('profile_view')
    return render(request, 'maintenance/profile.html', {'profile': profile})