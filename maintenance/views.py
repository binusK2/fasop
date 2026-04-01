from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from devices.permissions import require_can_edit, require_can_delete, is_viewer_only
from .models import Maintenance, MaintenancePLC, MaintenanceRouter, MaintenanceRadio, MaintenanceVoIP, MaintenanceMux, MaintenanceRectifier, MaintenanceTeleproteksi
from .forms import MaintenanceForm, MaintenancePLCForm, MaintenanceRouterForm, MaintenanceRadioForm, MaintenanceVoIPForm, MaintenanceMuxForm, MaintenanceRectifierForm, MaintenanceTeleproteksiForm
from devices.models import Device, DeviceType
from gangguan.models import Gangguan
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
    'TELEPROTEKSI':        (MaintenanceTeleproteksiForm, 'maintenance/teleproteksi_form.html'),
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
            maintenance.maintenance_type = 'Preventive'  # FIX: disabled widget tidak dikirim browser
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
        old_status = maintenance.status
        maintenance.status = request.POST.get('status')
        maintenance.save()
        # Notif ke AM kalau baru selesai (Done) dan perlu TTD
        if old_status != 'Done' and maintenance.status == 'Done':
            try:
                from notifikasi.views import notif_ke_am
                notif_ke_am(
                    tipe   = 'maintenance_ttd',
                    judul  = f'Maintenance selesai — {maintenance.device.nama}',
                    pesan  = (
                        f'Maintenance {maintenance.maintenance_type} pada '
                        f'{maintenance.device.nama} ({maintenance.device.lokasi}) '
                        f'tanggal {maintenance.date.strftime("%d %b %Y")} '
                        f'telah selesai dan memerlukan pengesahan.'
                    ),
                    level  = 'info',
                    url    = f'/maintenance/view/{maintenance.pk}/',
                    device = maintenance.device,
                )
            except Exception:
                pass
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
    tp_detail     = None

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

    elif device_type == 'TELEPROTEKSI':
        try:
            tp_detail = maintenance.maintenanceteleproteksi
        except MaintenanceTeleproteksi.DoesNotExist:
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
        'tp_detail':        tp_detail,
        'tp_akses_list':    [
            ('Akses TP',        tp_detail.akses_tp        if tp_detail else ''),
            ('Remote Akses TP', tp_detail.remote_akses_tp if tp_detail else ''),
        ] if tp_detail else [],
        'tp_skema_list': [
            {'n': n, 'command': getattr(tp_detail, f'skema_{n}_command', ''),
             'send_minus': getattr(tp_detail, f'skema_{n}_send_minus', None),
             'send_plus':  getattr(tp_detail, f'skema_{n}_send_plus',  None),
             'receive_minus': getattr(tp_detail, f'skema_{n}_receive_minus', None),
             'receive_plus':  getattr(tp_detail, f'skema_{n}_receive_plus',  None),
            } for n in range(1, 5)
        ] if tp_detail else [],
        'tp_uji_list': [
            ('Send Command 1',    tp_detail.skema_1_send_result    if tp_detail else ''),
            ('Receive Command 1', tp_detail.skema_1_receive_result if tp_detail else ''),
            ('Send Command 2',    tp_detail.skema_2_send_result    if tp_detail else ''),
            ('Receive Command 2', tp_detail.skema_2_receive_result if tp_detail else ''),
            ('Send Command 3',    tp_detail.skema_3_send_result    if tp_detail else ''),
            ('Receive Command 3', tp_detail.skema_3_receive_result if tp_detail else ''),
            ('Send Command 4',    tp_detail.skema_4_send_result    if tp_detail else ''),
            ('Receive Command 4', tp_detail.skema_4_receive_result if tp_detail else ''),
        ] if tp_detail else [],
    })




# ─────────────────────────────────────────────────────────────────────
# EDIT  (hanya status Open)
# ─────────────────────────────────────────────────────────────────────
@login_required
def maintenance_edit(request, pk):
    maintenance = get_object_or_404(Maintenance, pk=pk)
    # Corrective punya form & flow sendiri — jangan campur dengan preventive
    if maintenance.maintenance_type == 'Corrective':
        return redirect('corrective_edit', pk=pk)
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
            elif detail_form_class.__name__ == 'MaintenanceTeleproteksiForm':
                detail_instance = maintenance.maintenanceteleproteksi
        except Exception:
            pass

    # Gunakan template edit yang sama dengan create
    edit_template = template  # reuse template yang sama

    if request.method == 'POST':
        mform = MaintenanceForm(request.POST, request.FILES, instance=maintenance)
        dform = detail_form_class(request.POST, instance=detail_instance) if detail_form_class else None

        if mform.is_valid() and (dform is None or dform.is_valid()):
            m = mform.save(commit=False)
            m.maintenance_type = 'Preventive'  # FIX: pastikan tidak hilang
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
@require_can_delete
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
    # Coba WeasyPrint dulu, fallback ke ReportLab jika tidak tersedia
    try:
        from .pdf_weasy import build_pdf_weasy as build_pdf
    except (ImportError, OSError):
        from .pdf_export import build_pdf

    maintenance = get_object_or_404(Maintenance, pk=pk)
    device      = maintenance.device
    device_kind = device.jenis.name.strip().upper() if device.jenis else 'GENERIC'

    # ── Ambil detail sesuai jenis ──────────────────────────────────
    router_detail = plc_detail = radio_detail = None
    voip_detail = mux_detail = rect_detail = tp_detail = None

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
    elif device_kind == 'TELEPROTEKSI':
        tp_detail = _try(lambda: maintenance.maintenanceteleproteksi)

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

        'tp': {
            'suhu_ruangan':       _g(tp_detail, 'suhu_ruangan'),
            'kebersihan_perangkat': _g(tp_detail, 'kebersihan_perangkat', ''),
            'kebersihan_panel':   _g(tp_detail, 'kebersihan_panel', ''),
            'lampu':              _g(tp_detail, 'lampu', ''),
            'link':               _g(tp_detail, 'link', ''),
            'tipe_tp':            _g(tp_detail, 'tipe_tp', ''),
            'versi_program':      _g(tp_detail, 'versi_program', ''),
            'address_tp':         _g(tp_detail, 'address_tp', ''),
            'port_comm':          _g(tp_detail, 'port_comm', ''),
            'akses_tp':           _g(tp_detail, 'akses_tp', ''),
            'remote_akses_tp':    _g(tp_detail, 'remote_akses_tp', ''),
            'jumlah_skema':       _g(tp_detail, 'jumlah_skema'),
            'skema_1_command':    _g(tp_detail, 'skema_1_command', ''),
            'skema_1_send_minus': _g(tp_detail, 'skema_1_send_minus'),
            'skema_1_send_plus':  _g(tp_detail, 'skema_1_send_plus'),
            'skema_1_receive_minus': _g(tp_detail, 'skema_1_receive_minus'),
            'skema_1_receive_plus':  _g(tp_detail, 'skema_1_receive_plus'),
            'skema_2_command':    _g(tp_detail, 'skema_2_command', ''),
            'skema_2_send_minus': _g(tp_detail, 'skema_2_send_minus'),
            'skema_2_send_plus':  _g(tp_detail, 'skema_2_send_plus'),
            'skema_2_receive_minus': _g(tp_detail, 'skema_2_receive_minus'),
            'skema_2_receive_plus':  _g(tp_detail, 'skema_2_receive_plus'),
            'skema_3_command':    _g(tp_detail, 'skema_3_command', ''),
            'skema_3_send_minus': _g(tp_detail, 'skema_3_send_minus'),
            'skema_3_send_plus':  _g(tp_detail, 'skema_3_send_plus'),
            'skema_3_receive_minus': _g(tp_detail, 'skema_3_receive_minus'),
            'skema_3_receive_plus':  _g(tp_detail, 'skema_3_receive_plus'),
            'skema_4_command':    _g(tp_detail, 'skema_4_command', ''),
            'skema_4_send_minus': _g(tp_detail, 'skema_4_send_minus'),
            'skema_4_send_plus':  _g(tp_detail, 'skema_4_send_plus'),
            'skema_4_receive_minus': _g(tp_detail, 'skema_4_receive_minus'),
            'skema_4_receive_plus':  _g(tp_detail, 'skema_4_receive_plus'),
            'skema_1_send_result':    _g(tp_detail, 'skema_1_send_result', ''),
            'skema_1_receive_result': _g(tp_detail, 'skema_1_receive_result', ''),
            'skema_2_send_result':    _g(tp_detail, 'skema_2_send_result', ''),
            'skema_2_receive_result': _g(tp_detail, 'skema_2_receive_result', ''),
            'skema_3_send_result':    _g(tp_detail, 'skema_3_send_result', ''),
            'skema_3_receive_result': _g(tp_detail, 'skema_3_receive_result', ''),
            'skema_4_send_result':    _g(tp_detail, 'skema_4_send_result', ''),
            'skema_4_receive_result': _g(tp_detail, 'skema_4_receive_result', ''),
            'time_sync':          _g(tp_detail, 'time_sync', ''),
            'loop_test':          _g(tp_detail, 'loop_test'),
            'catatan':            _g(tp_detail, 'catatan', ''),
        } if tp_detail else {},
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
            nama_lengkap = request.POST.get('display_name', '').strip()
            profile.display_name = nama_lengkap
            profile.save(update_fields=['display_name'])
            # Sync ke User.first_name / last_name agar get_full_name() ikut terupdate
            parts = nama_lengkap.split(' ', 1)
            request.user.first_name = parts[0]
            request.user.last_name  = parts[1] if len(parts) > 1 else ''
            request.user.save(update_fields=['first_name', 'last_name'])
            messages.success(request, f'Nama lengkap berhasil disimpan sebagai "{nama_lengkap}".')
        return redirect('profile_view')
    return render(request, 'maintenance/profile.html', {'profile': profile})

# ─────────────────────────────────────────────────────────────
# CORRECTIVE MAINTENANCE VIEWS
# ─────────────────────────────────────────────────────────────

@login_required
@require_can_edit
def corrective_add(request, device_id=None, gangguan_id=None):
    """
    Form corrective maintenance ringkas.
    Bisa diakses dari:
      - Menu maintenance umum (GET /maintenance/corrective/add/)
      - Device detail (GET /maintenance/corrective/device/<id>/)
      - Gangguan detail (GET /maintenance/corrective/gangguan/<id>/)
    """
    from maintenance.models import MaintenanceCorrective
    from devices.models import Device
    from gangguan.models import Gangguan

    # Pre-fill device & gangguan jika dari context tertentu
    device_init   = Device.objects.filter(pk=device_id, is_deleted=False).first() if device_id else None
    gangguan_init = Gangguan.objects.filter(pk=gangguan_id).first() if gangguan_id else None
    # Kalau dari gangguan, device dari gangguan.peralatan
    if gangguan_init and not device_init and gangguan_init.peralatan:
        device_init = gangguan_init.peralatan

    if request.method == 'POST':
        # ── Ambil data form ──
        device_pk         = request.POST.get('device_id')
        tanggal           = request.POST.get('tanggal', '')
        # Pelaksana dari tag-input JS (JSON array)
        import json as _json
        _raw_pel = request.POST.get('pelaksana_names_input', '[]')
        try:
            pelaksana_list = _json.loads(_raw_pel)
        except Exception:
            pelaksana_list = [n.strip() for n in request.POST.get('pelaksana_names', '').split(',') if n.strip()]
        jenis_kerusakan   = request.POST.get('jenis_kerusakan', '')
        deskripsi_masalah = request.POST.get('deskripsi_masalah', '').strip()
        tindakan          = request.POST.get('tindakan', '').strip()
        komponen_diganti  = request.POST.get('komponen_diganti') == 'on'
        nama_komponen     = request.POST.get('nama_komponen', '').strip()
        komponen_terkait_pk = request.POST.get('komponen_terkait', '') or None
        kondisi_sebelum   = request.POST.get('kondisi_sebelum', '').strip()
        kondisi_sesudah   = request.POST.get('kondisi_sesudah', '').strip()
        durasi_jam        = request.POST.get('durasi_jam', '') or None
        durasi_menit      = request.POST.get('durasi_menit', '') or None
        status_perbaikan  = request.POST.get('status_perbaikan', 'selesai')
        gangguan_pk       = request.POST.get('gangguan_id', '') or None
        update_gangguan   = request.POST.get('update_gangguan', '')
        status_gangguan   = request.POST.get('status_gangguan', '')
        foto_sebelum      = request.FILES.get('foto_sebelum')
        foto_sesudah      = request.FILES.get('foto_sesudah')

        device = Device.objects.filter(pk=device_pk, is_deleted=False).first()
        if not device:
            device = device_init

        # Resolve komponen_terkait dari DeviceComponent
        from devices.models_komponen import DeviceComponent
        komponen_terkait_obj = None
        if komponen_terkait_pk:
            komponen_terkait_obj = DeviceComponent.objects.filter(pk=komponen_terkait_pk).first()

        if device and tanggal and deskripsi_masalah and tindakan:
            from datetime import datetime
            # Buat Maintenance record
            m_status = 'Done' if status_perbaikan == 'selesai' else 'Open'
            maint = Maintenance.objects.create(
                device           = device,
                maintenance_type = 'Corrective',
                date             = tanggal,
                description      = deskripsi_masalah,
                status           = m_status,
                pelaksana_names  = pelaksana_list,
            )

            # Buat detail corrective
            gangguan_obj = Gangguan.objects.filter(pk=gangguan_pk).first() if gangguan_pk else gangguan_init
            corr = MaintenanceCorrective(
                maintenance       = maint,
                gangguan          = gangguan_obj,
                jenis_kerusakan   = jenis_kerusakan,
                deskripsi_masalah = deskripsi_masalah,
                tindakan          = tindakan,
                komponen_diganti  = komponen_diganti,
                nama_komponen     = nama_komponen,
                komponen_terkait  = komponen_terkait_obj,
                kondisi_sebelum   = kondisi_sebelum,
                kondisi_sesudah   = kondisi_sesudah,
                durasi_jam        = int(durasi_jam) if durasi_jam else None,
                durasi_menit      = int(durasi_menit) if durasi_menit else None,
                status_perbaikan  = status_perbaikan,
            )
            if foto_sebelum: corr.foto_sebelum = foto_sebelum
            if foto_sesudah: corr.foto_sesudah = foto_sesudah
            corr.save()

            # Auto DeviceEvent kalau ada komponen diganti
            if komponen_diganti and nama_komponen:
                from devices.models import DeviceEvent
                from datetime import date as _date
                DeviceEvent.objects.create(
                    device         = device,
                    tipe           = 'penggantian',
                    tanggal        = tanggal[:10] if tanggal else _date.today(),
                    komponen       = nama_komponen,
                    nilai_lama     = kondisi_sebelum,
                    nilai_baru     = kondisi_sesudah,
                    catatan        = f'Dari corrective maintenance — {deskripsi_masalah[:100]}',
                    dilakukan_oleh = request.user,
                    gangguan       = gangguan_obj,
                )

                # Auto-update status DeviceComponent jika komponen_terkait dipilih
                if komponen_terkait_obj:
                    from django.utils import timezone as _tz
                    komponen_terkait_obj.status = 'diganti'
                    komponen_terkait_obj.tanggal_ganti = _tz.localdate()
                    komponen_terkait_obj.save(update_fields=['status', 'tanggal_ganti', 'updated_at'])

            # Update status gangguan jika diminta
            if gangguan_obj and update_gangguan and status_gangguan:
                gangguan_obj.status = status_gangguan
                if status_gangguan in ('resolved', 'closed') and not gangguan_obj.tanggal_resolved:
                    from django.utils import timezone
                    gangguan_obj.tanggal_resolved = timezone.now()
                gangguan_obj.save()

            # Notif ke AM — corrective selesai
            if status_perbaikan == 'selesai':
                try:
                    from notifikasi.views import notif_ke_am
                    g_info = f' (Tiket {gangguan_obj.nomor_gangguan})' if gangguan_obj else ''
                    notif_ke_am(
                        tipe   = 'corrective_selesai',
                        judul  = f'Corrective selesai — {device.nama}',
                        pesan  = (
                            f'Tindakan perbaikan pada {device.nama} ({device.lokasi})'
                            f'{g_info} telah selesai. Tindakan: {tindakan[:100]}'
                        ),
                        level  = 'success',
                        url    = f'/maintenance/view/{maint.pk}/',
                        device = device,
                    )
                except Exception:
                    pass

            # Redirect sesuai konteks
            if gangguan_obj and update_gangguan:
                return redirect('gangguan_detail', pk=gangguan_obj.pk)
            if gangguan_id:
                return redirect('gangguan_detail', pk=gangguan_id)
            if device_id:
                return redirect('device_view', pk=device_id)
            return redirect('maintenance_list')

    # Daftar gangguan aktif untuk dropdown
    from gangguan.models import Gangguan
    gangguan_aktif = Gangguan.objects.filter(
        status__in=['open', 'in_progress']
    ).order_by('-tanggal_gangguan')

    devices = Device.objects.filter(is_deleted=False).select_related('jenis').order_by('lokasi', 'nama')

    from datetime import date as _date
    return render(request, 'maintenance/corrective_form.html', {
        'device_init':    device_init,
        'gangguan_init':  gangguan_init,
        'gangguan_aktif': gangguan_aktif,
        'devices':        devices,
        'today_date':     _date.today().strftime('%Y-%m-%dT%H:%M'),
        'from_gangguan':  gangguan_id is not None,
        'from_device':    device_id is not None,
    })


@login_required
@require_can_edit
def corrective_edit(request, pk):
    """Edit corrective maintenance yang sudah ada."""
    from maintenance.models import MaintenanceCorrective
    from gangguan.models import Gangguan

    maintenance = get_object_or_404(Maintenance, pk=pk)
    if maintenance.maintenance_type != 'Corrective':
        return redirect('maintenance_edit', pk=pk)

    device = maintenance.device
    try:
        corr = maintenance.corrective_detail
    except Exception:
        corr = None

    if request.method == 'POST':
        tanggal           = request.POST.get('tanggal', '')
        import json as _jn
        _raw2 = request.POST.get('pelaksana_names_input', '[]')
        try:
            pelaksana_list = _jn.loads(_raw2)
        except Exception:
            pelaksana_list = [n.strip() for n in request.POST.get('pelaksana_names', '').split(',') if n.strip()]
        jenis_kerusakan   = request.POST.get('jenis_kerusakan', '')
        deskripsi_masalah = request.POST.get('deskripsi_masalah', '').strip()
        tindakan          = request.POST.get('tindakan', '').strip()
        komponen_diganti  = request.POST.get('komponen_diganti') == 'on'
        nama_komponen     = request.POST.get('nama_komponen', '').strip()
        komponen_terkait_pk = request.POST.get('komponen_terkait', '') or None
        kondisi_sebelum   = request.POST.get('kondisi_sebelum', '').strip()
        kondisi_sesudah   = request.POST.get('kondisi_sesudah', '').strip()
        durasi_jam        = request.POST.get('durasi_jam', '') or None
        durasi_menit      = request.POST.get('durasi_menit', '') or None
        status_perbaikan  = request.POST.get('status_perbaikan', 'selesai')
        gangguan_pk       = request.POST.get('gangguan_id', '') or None
        update_gangguan   = request.POST.get('update_gangguan', '')
        status_gangguan   = request.POST.get('status_gangguan', '')
        foto_sebelum      = request.FILES.get('foto_sebelum')
        foto_sesudah      = request.FILES.get('foto_sesudah')

        # Resolve komponen_terkait dari DeviceComponent
        from devices.models_komponen import DeviceComponent
        komponen_terkait_obj = None
        if komponen_terkait_pk:
            komponen_terkait_obj = DeviceComponent.objects.filter(pk=komponen_terkait_pk).first()

        if tanggal and deskripsi_masalah and tindakan:
            m_status = 'Done' if status_perbaikan == 'selesai' else 'Open'
            maintenance.date        = tanggal
            maintenance.description = deskripsi_masalah
            maintenance.status      = m_status
            maintenance.pelaksana_names = pelaksana_list
            maintenance.save()

            gangguan_obj = Gangguan.objects.filter(pk=gangguan_pk).first() if gangguan_pk else (corr.gangguan if corr else None)
            if corr is None:
                corr = MaintenanceCorrective(maintenance=maintenance)
            corr.gangguan          = gangguan_obj
            corr.jenis_kerusakan   = jenis_kerusakan
            corr.deskripsi_masalah = deskripsi_masalah
            corr.tindakan          = tindakan
            corr.komponen_diganti  = komponen_diganti
            corr.nama_komponen     = nama_komponen
            corr.komponen_terkait  = komponen_terkait_obj
            corr.kondisi_sebelum   = kondisi_sebelum
            corr.kondisi_sesudah   = kondisi_sesudah
            corr.durasi_jam        = int(durasi_jam) if durasi_jam else None
            corr.durasi_menit      = int(durasi_menit) if durasi_menit else None
            corr.status_perbaikan  = status_perbaikan
            if foto_sebelum: corr.foto_sebelum = foto_sebelum
            if foto_sesudah: corr.foto_sesudah = foto_sesudah
            corr.save()

            # Auto-update status DeviceComponent jika komponen diganti
            if komponen_diganti and komponen_terkait_obj:
                from django.utils import timezone as _tz
                komponen_terkait_obj.status = 'diganti'
                komponen_terkait_obj.tanggal_ganti = _tz.localdate()
                komponen_terkait_obj.save(update_fields=['status', 'tanggal_ganti', 'updated_at'])

            if gangguan_obj and update_gangguan and status_gangguan:
                gangguan_obj.status = status_gangguan
                if status_gangguan in ('resolved', 'closed') and not gangguan_obj.tanggal_resolved:
                    from django.utils import timezone
                    gangguan_obj.tanggal_resolved = timezone.now()
                gangguan_obj.save()

            return redirect('maintenance_view', pk=pk)

    # Nilai awal untuk pre-fill form
    tanggal_init = ''
    if maintenance.date:
        try:
            import pytz
            from django.conf import settings as dj_settings
            tz = pytz.timezone(dj_settings.TIME_ZONE)
            local_dt = maintenance.date.astimezone(tz) if maintenance.date.tzinfo else maintenance.date
            tanggal_init = local_dt.strftime('%Y-%m-%dT%H:%M')
        except Exception:
            tanggal_init = str(maintenance.date)[:16].replace(' ', 'T')

    pelaksana_init = ', '.join(maintenance.pelaksana_names or [])
    gangguan_init  = corr.gangguan if corr else None

    gangguan_aktif = Gangguan.objects.filter(
        status__in=['open', 'in_progress']
    ).order_by('-tanggal_gangguan')

    return render(request, 'maintenance/corrective_form.html', {
        'is_edit':            True,
        'maintenance':        maintenance,
        'corr':               corr,
        'device_init':        device,
        'gangguan_init':      gangguan_init,
        'gangguan_aktif':     gangguan_aktif,
        'today_date':         tanggal_init,
        'pelaksana_init':     pelaksana_init,
        'pelaksana_init_json': __import__('json').dumps(maintenance.pelaksana_names or []),
        'from_gangguan':      False,
        'from_device':        False,
    })


# ─────────────────────────────────────────────────────────────
# OFFLINE FORM: Download Template & Import Excel
# ─────────────────────────────────────────────────────────────

@login_required
def offline_form_download(request):
    """Download template Excel maintenance per lokasi, sheet per jenis perangkat."""
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter
    from openpyxl.worksheet.datavalidation import DataValidation

    # ── Ambil parameter lokasi ──────────────────────────────────────
    selected_lokasi = request.GET.get('lokasi', '').strip()

    wb = Workbook()
    wb.remove(wb.active)  # hapus sheet default

    # ── Style helpers ───────────────────────────────────────────────
    def hfont(color='FFFFFF'): return Font(bold=True, color=color, size=10, name='Arial')
    def hfill(hex_): return PatternFill('solid', fgColor=hex_)
    border = Border(
        left=Side(style='thin'), right=Side(style='thin'),
        top=Side(style='thin'), bottom=Side(style='thin')
    )
    wrap = Alignment(wrap_text=True, vertical='top')
    center = Alignment(horizontal='center', vertical='center', wrap_text=True)

    def style_header(ws, row, cols_cfg, fill_hex):
        """cols_cfg: list of (col_letter, title, width)"""
        for col_letter, title, width in cols_cfg:
            c = ws[f'{col_letter}{row}']
            c.value = title
            c.font = hfont()
            c.fill = hfill(fill_hex)
            c.alignment = center
            c.border = border
            ws.column_dimensions[col_letter].width = width

    def add_border_rows(ws, start_row, end_row, cols_cfg):
        for row in range(start_row, end_row + 1):
            for col_letter, _, _ in cols_cfg:
                c = ws[f'{col_letter}{row}']
                c.border = border
                c.alignment = wrap

    def dv(ws, type_, formula, cell_range, blank=True):
        d = DataValidation(type=type_, formula1=formula, allow_blank=blank)
        ws.add_data_validation(d)
        d.add(cell_range)
        return d

    def info_row(ws, row, text, ncols):
        last = get_column_letter(ncols)
        ws.merge_cells(f'A{row}:{last}{row}')
        c = ws[f'A{row}']
        c.value = text
        c.font = Font(italic=True, color='1E40AF', size=9, name='Arial')
        c.fill = hfill('DBEAFE')
        c.alignment = Alignment(horizontal='left', vertical='center', wrap_text=True)
        ws.row_dimensions[row].height = 28

    def title_row(ws, row, text, ncols, fill='EFF6FF', fcolor='1E40AF'):
        last = get_column_letter(ncols)
        ws.merge_cells(f'A{row}:{last}{row}')
        c = ws[f'A{row}']
        c.value = text
        c.font = Font(bold=True, size=11, name='Arial', color=fcolor)
        c.fill = hfill(fill)
        c.alignment = center
        ws.row_dimensions[row].height = 28

    # ── Query perangkat ──────────────────────────────────────────────
    qs = Device.objects.filter(is_deleted=False).select_related('jenis').order_by('nama')
    if selected_lokasi:
        qs = qs.filter(lokasi=selected_lokasi)

    # Kelompokkan per jenis
    from collections import defaultdict
    by_jenis = defaultdict(list)
    for d in qs:
        jenis_name = d.jenis.name.strip().upper() if d.jenis else 'LAINNYA'
        by_jenis[jenis_name].append(d)

    # ── Helper: buat sheet per jenis ────────────────────────────────
    OK_NOK = '"OK,NOK"'
    BERSIH_KOTOR = '"Bersih,Kotor"'

    def make_sheet_router(devices):
        ws = wb.create_sheet('Router & Switch')
        ws.sheet_properties.tabColor = '3B82F6'
        cols = [
            ('A','Nama Perangkat',22),('B','Tanggal (YYYY-MM-DD HH:MM)',22),
            ('C','Pelaksana (pisah koma)',22),('D','Deskripsi',30),
            ('E','Kondisi Fisik Unit',15),('F','Indikator LED',15),('G','Kondisi Kabel',15),
            ('H','Teg Input (V)',13),('I','Suhu Perangkat (°C)',14),
            ('J','CPU Load (%)',12),('K','Memory Usage (%)',14),
            ('L','Port Aktif',10),('M','Port Total',10),
            ('N','IP/Routing Status',15),('O','Catatan Tambahan',30),
        ]
        title_row(ws,1,'TEMPLATE PREVENTIVE — ROUTER & SWITCH',len(cols),'EFF6FF','1E40AF')
        info_row(ws,2,'Kolom bertanda (*) wajib diisi. Nama perangkat sudah pre-filled sesuai lokasi.',len(cols))
        style_header(ws,3,cols,'3B82F6')
        ws.freeze_panes='A4'
        for i,d in enumerate(devices,start=4):
            ws[f'A{i}'] = d.nama
            ws[f'A{i}'].font = Font(bold=True,name='Arial',size=9)
        add_border_rows(ws,4,4+max(len(devices),20)-1,cols)
        for col,formula in [('E',OK_NOK),('F',OK_NOK),('G',OK_NOK),('N',OK_NOK)]:
            dv(ws,'list',formula,f'{col}4:{col}{4+len(devices)+5}')

    def make_sheet_plc(devices):
        ws = wb.create_sheet('PLC')
        ws.sheet_properties.tabColor = '8B5CF6'
        cols = [
            ('A','Nama Perangkat',22),('B','Tanggal (YYYY-MM-DD HH:MM)',22),
            ('C','Pelaksana (pisah koma)',22),('D','Deskripsi',30),
            ('E','Akses PLC',12),('F','Remote Akses PLC',15),
            ('G','Transmission Line (dBm)',18),('H','RX Pilot Level (dBm)',18),
            ('I','Freq TX (MHz)',13),('J','BW TX (MHz)',12),
            ('K','Freq RX (MHz)',13),('L','BW RX (MHz)',12),
            ('M','Time Sync',12),('N','Wave Trap',12),('O','IMU',10),
            ('P','Kabel Coaxial',14),
        ]
        title_row(ws,1,'TEMPLATE PREVENTIVE — PLC',len(cols),'F5F3FF','4C1D95')
        info_row(ws,2,'Kolom OK/NOK gunakan dropdown.',len(cols))
        style_header(ws,3,cols,'8B5CF6')
        ws.freeze_panes='A4'
        for i,d in enumerate(devices,start=4):
            ws[f'A{i}'] = d.nama
            ws[f'A{i}'].font = Font(bold=True,name='Arial',size=9)
        add_border_rows(ws,4,4+max(len(devices),15)-1,cols)
        for col in ['E','F','M','N','O','P']:
            dv(ws,'list',OK_NOK,f'{col}4:{col}{4+len(devices)+5}')

    def make_sheet_radio(devices):
        ws = wb.create_sheet('Radio')
        ws.sheet_properties.tabColor = 'F59E0B'
        cols = [
            ('A','Nama Perangkat',22),('B','Tanggal (YYYY-MM-DD HH:MM)',22),
            ('C','Pelaksana (pisah koma)',22),('D','Deskripsi',30),
            ('E','Suhu Ruangan (°C)',15),('F','Kebersihan',13),('G','Lampu Penerangan',16),
            ('H','Ada Radio',12),('I','Ada Battery',12),('J','Merk Battery',18),
            ('K','Ada Power Supply',15),('L','Merk PSU',18),
            ('M','Jenis Antena',15),('N','SWR',10),
            ('O','Power TX (W)',12),('P','Teg Battery (V)',14),
            ('Q','Teg PSU (V)',12),('R','Frek TX (MHz)',13),('S','Frek RX (MHz)',13),
            ('T','Catatan',30),
        ]
        title_row(ws,1,'TEMPLATE PREVENTIVE — RADIO',len(cols),'FFFBEB','92400E')
        info_row(ws,2,'Gunakan dropdown untuk kolom pilihan.',len(cols))
        style_header(ws,3,cols,'F59E0B')
        ws.freeze_panes='A4'
        for i,d in enumerate(devices,start=4):
            ws[f'A{i}'] = d.nama
            ws[f'A{i}'].font = Font(bold=True,name='Arial',size=9)
        add_border_rows(ws,4,4+max(len(devices),15)-1,cols)
        for col in ['H','I','K']:
            dv(ws,'list',OK_NOK,f'{col}4:{col}{4+len(devices)+5}')
        dv(ws,'list',BERSIH_KOTOR,f'F4:F{4+len(devices)+5}')
        dv(ws,'list','"Menyala,Tidak Menyala,Redup,Tidak Ada"',f'G4:G{4+len(devices)+5}')
        dv(ws,'list','"Directional,Bidirectional"',f'M4:M{4+len(devices)+5}')
        dv(ws,'list','"<1.5,>1.5"',f'N4:N{4+len(devices)+5}')

    def make_sheet_voip(devices):
        ws = wb.create_sheet('VoIP')
        ws.sheet_properties.tabColor = '8B5CF6'
        cols = [
            ('A','Nama Perangkat',22),('B','Tanggal (YYYY-MM-DD HH:MM)',22),
            ('C','Pelaksana (pisah koma)',22),('D','Deskripsi',30),
            ('E','IP Address',18),('F','Extension Number',16),
            ('G','SIP Server 1',20),('H','SIP Server 2',20),
            ('I','Suhu Ruangan (°C)',15),
            ('J','Kondisi Fisik',14),('K','NTP Server',12),('L','Web Config',12),
            ('M','Merk PSU',18),('N','Teg Input PSU (V)',15),('O','Status PSU',12),
            ('P','Catatan',30),
        ]
        title_row(ws,1,'TEMPLATE PREVENTIVE — VoIP',len(cols),'F5F3FF','5B21B6')
        info_row(ws,2,'Gunakan dropdown untuk kolom OK/NOK.',len(cols))
        style_header(ws,3,cols,'8B5CF6')
        ws.freeze_panes='A4'
        for i,d in enumerate(devices,start=4):
            ws[f'A{i}'] = d.nama
            ws[f'A{i}'].font = Font(bold=True,name='Arial',size=9)
        add_border_rows(ws,4,4+max(len(devices),15)-1,cols)
        for col in ['J','K','L','O']:
            dv(ws,'list',OK_NOK,f'{col}4:{col}{4+len(devices)+5}')

    def make_sheet_mux(devices):
        ws = wb.create_sheet('Multiplexer')
        ws.sheet_properties.tabColor = '10B981'
        cols = [
            ('A','Nama Perangkat',22),('B','Tanggal (YYYY-MM-DD HH:MM)',22),
            ('C','Pelaksana (pisah koma)',22),('D','Deskripsi',30),
            ('E','Suhu Ruangan (°C)',15),('F','Kebersihan',13),('G','Lampu',14),
            ('H','Brand',18),('I','Firmware',18),
            ('J','Sync Source 1',18),('K','Sync Source 2',18),
            ('L','HS1 TX (dBm)',13),('M','HS1 RX (dBm)',13),('N','HS1 Jarak (km)',14),
            ('O','HS2 TX (dBm)',13),('P','HS2 RX (dBm)',13),('Q','HS2 Jarak (km)',14),
            ('R','PSU1 Status',13),('S','PSU2 Status',13),('T','FAN Status',12),
            ('U','Catatan',30),
        ]
        title_row(ws,1,'TEMPLATE PREVENTIVE — MULTIPLEXER',len(cols),'ECFDF5','065F46')
        info_row(ws,2,'Gunakan dropdown untuk kolom pilihan.',len(cols))
        style_header(ws,3,cols,'10B981')
        ws.freeze_panes='A4'
        for i,d in enumerate(devices,start=4):
            ws[f'A{i}'] = d.nama
            ws[f'A{i}'].font = Font(bold=True,name='Arial',size=9)
        add_border_rows(ws,4,4+max(len(devices),15)-1,cols)
        for col in ['R','S','T']:
            dv(ws,'list',OK_NOK,f'{col}4:{col}{4+len(devices)+5}')
        dv(ws,'list',BERSIH_KOTOR,f'F4:F{4+len(devices)+5}')
        dv(ws,'list','"Menyala,Tidak Menyala,Redup"',f'G4:G{4+len(devices)+5}')

    def make_sheet_rectifier(devices):
        ws = wb.create_sheet('Catu Daya & Rectifier')
        ws.sheet_properties.tabColor = 'F97316'
        cols = [
            ('A','Nama Perangkat',22),('B','Tanggal (YYYY-MM-DD HH:MM)',22),
            ('C','Pelaksana (pisah koma)',22),('D','Deskripsi',30),
            ('E','Suhu Ruangan (°C)',15),('F','Exhaust Fan',18),
            ('G','Kebersihan',13),('H','Lampu',13),
            ('I','Rect Merk',18),('J','Rect Tipe',18),('K','Rect Kondisi',14),
            ('L','V Rectifier (V)',15),('M','V Battery (V)',14),
            ('N','Teg(+) GND (V)',14),('O','Teg(-) GND (V)',14),
            ('P','V Dropper (V)',13),('Q','A Rectifier (A)',14),
            ('R','A Battery (A)',13),('S','A Load (A)',12),
            ('T','Bat Merk',18),('U','Bat Tipe',18),('V','Bat Kondisi',14),
            ('W','Jumlah Cell',12),('X','V Total Bank (V)',15),
            ('Y','Catatan',30),
        ]
        title_row(ws,1,'TEMPLATE PREVENTIVE — CATU DAYA & RECTIFIER',len(cols),'FFF7ED','9A3412')
        info_row(ws,2,'Gunakan dropdown untuk kolom pilihan.',len(cols))
        style_header(ws,3,cols,'F97316')
        ws.freeze_panes='A4'
        for i,d in enumerate(devices,start=4):
            ws[f'A{i}'] = d.nama
            ws[f'A{i}'].font = Font(bold=True,name='Arial',size=9)
        add_border_rows(ws,4,4+max(len(devices),15)-1,cols)
        for col in ['K','V']:
            dv(ws,'list',OK_NOK,f'{col}4:{col}{4+len(devices)+5}')
        dv(ws,'list',BERSIH_KOTOR,f'G4:G{4+len(devices)+5}')
        dv(ws,'list','"Menyala,Tidak Menyala,Redup"',f'H4:H{4+len(devices)+5}')
        dv(ws,'list','"Terpasang,Tidak Terpasang,Rusak"',f'F4:F{4+len(devices)+5}')

    def make_sheet_teleproteksi(devices):
        ws = wb.create_sheet('Teleproteksi')
        ws.sheet_properties.tabColor = '6366F1'
        cols = [
            ('A','Nama Perangkat',22),('B','Tanggal (YYYY-MM-DD HH:MM)',22),
            ('C','Pelaksana (pisah koma)',22),('D','Deskripsi',30),
            ('E','Suhu Ruangan (°C)',15),('F','Kebersihan Perangkat',18),
            ('G','Kebersihan Panel',16),('H','Lampu',12),
            ('I','Link (Terhubung ke)',25),('J','Tipe TP',13),
            ('K','Port Comm',12),('L','Versi Program',16),('M','Address TP',14),
            ('N','Akses TP',12),('O','Remote Akses TP',16),
            ('P','Jml Skema',11),
            ('Q','Skema 1 Command',18),('R','S1 Send(-)',12),('S','S1 Send(+)',12),
            ('T','S1 Recv(-)',12),('U','S1 Recv(+)',12),
            ('V','Skema 2 Command',18),('W','S2 Send(-)',12),('X','S2 Send(+)',12),
            ('Y','S2 Recv(-)',12),('Z','S2 Recv(+)',12),
            ('AA','Skema 3 Command',18),('AB','S3 Send(-)',12),('AC','S3 Send(+)',12),
            ('AD','S3 Recv(-)',12),('AE','S3 Recv(+)',12),
            ('AF','Skema 4 Command',18),('AG','S4 Send(-)',12),('AH','S4 Send(+)',12),
            ('AI','S4 Recv(-)',12),('AJ','S4 Recv(+)',12),
            ('AK','Uji Send 1',12),('AL','Uji Recv 1',12),
            ('AM','Uji Send 2',12),('AN','Uji Recv 2',12),
            ('AO','Uji Send 3',12),('AP','Uji Recv 3',12),
            ('AQ','Uji Send 4',12),('AR','Uji Recv 4',12),
            ('AS','Time Sync',12),('AT','Loop Test (ms)',14),
            ('AU','Catatan',30),
        ]
        title_row(ws,1,'TEMPLATE PREVENTIVE — TELEPROTEKSI',len(cols),'EEF2FF','3730A3')
        info_row(ws,2,'Gunakan dropdown untuk kolom pilihan. Address TP hanya untuk tipe Digital.',len(cols))
        style_header(ws,3,cols,'6366F1')
        ws.freeze_panes='A4'
        for i,d in enumerate(devices,start=4):
            ws[f'A{i}'] = d.nama
            ws[f'A{i}'].font = Font(bold=True,name='Arial',size=9)
        add_border_rows(ws,4,4+max(len(devices),15)-1,cols)
        for col in ['N','O','AK','AL','AM','AN','AO','AP','AQ','AR','AS']:
            dv(ws,'list',OK_NOK,f'{col}4:{col}{4+len(devices)+5}')
        dv(ws,'list',BERSIH_KOTOR,f'F4:F{4+len(devices)+5}')
        dv(ws,'list',BERSIH_KOTOR,f'G4:G{4+len(devices)+5}')
        dv(ws,'list',OK_NOK,f'H4:H{4+len(devices)+5}')
        dv(ws,'list','"Digital,Analog"',f'J4:J{4+len(devices)+5}')
        dv(ws,'list','"E1,G64,E&M,PLC"',f'K4:K{4+len(devices)+5}')
        SKEMA_CMD = '"Distance,DEF,DTT,Tidak Terpakai"'
        for col in ['Q','V','AA','AF']:
            dv(ws,'list',SKEMA_CMD,f'{col}4:{col}{4+len(devices)+5}')

    def make_sheet_corrective(devices):
        ws = wb.create_sheet('Corrective')
        ws.sheet_properties.tabColor = 'EF4444'
        cols = [
            ('A','Nama Perangkat *',22),('B','Tanggal (YYYY-MM-DD HH:MM) *',22),
            ('C','Pelaksana (pisah koma)',22),('D','Jenis Kerusakan',18),
            ('E','Deskripsi Masalah',35),('F','Tindakan',35),
            ('G','Komponen Diganti (ya/tidak)',18),('H','Nama Komponen',22),
            ('I','Kondisi Sebelum',22),('J','Kondisi Sesudah',22),
            ('K','Status (selesai/perlu_tindaklanjut)',20),
        ]
        title_row(ws,1,'TEMPLATE CORRECTIVE MAINTENANCE',len(cols),'FEF2F2','991B1B')
        info_row(ws,2,'Kolom (*) wajib diisi. Nama perangkat harus PERSIS sama dengan di sistem.',len(cols))
        style_header(ws,3,cols,'EF4444')
        ws.freeze_panes='A4'
        # Pre-fill nama perangkat
        for i,d in enumerate(devices,start=4):
            ws[f'A{i}'] = d.nama
            ws[f'A{i}'].font = Font(bold=True,name='Arial',size=9)
        add_border_rows(ws,4,4+max(len(devices),20)-1,cols)
        dv(ws,'list','"hardware,software,power,komunikasi,mekanik,lainnya"',f'D4:D{4+len(devices)+10}')
        dv(ws,'list','"ya,tidak"',f'G4:G{4+len(devices)+10}')
        dv(ws,'list','"selesai,perlu_tindaklanjut"',f'K4:K{4+len(devices)+10}')

    # ── Buat sheet per jenis ─────────────────────────────────────────
    JENIS_SHEET_MAP = {
        'ROUTER':              make_sheet_router,
        'SWITCH':              make_sheet_router,
        'PLC':                 make_sheet_plc,
        'RADIO':               make_sheet_radio,
        'VOIP':                make_sheet_voip,
        'MULTIPLEXER':         make_sheet_mux,
        'RECTIFIER':           make_sheet_rectifier,
        'CATU DAYA':           make_sheet_rectifier,
        'CATUDAYA':            make_sheet_rectifier,
        'RECTIFIER & BATTERY': make_sheet_rectifier,
        'TELEPROTEKSI':        make_sheet_teleproteksi,
    }

    # Track sheet yang sudah dibuat (Router & Switch jadi satu)
    created_sheets = set()
    all_devices = list(qs)

    for jenis_key, func in JENIS_SHEET_MAP.items():
        devices_jenis = by_jenis.get(jenis_key, [])
        if not devices_jenis:
            continue
        sheet_name = {
            'SWITCH': 'Router & Switch',
            'ROUTER': 'Router & Switch',
            'CATU DAYA': 'Catu Daya & Rectifier',
            'CATUDAYA': 'Catu Daya & Rectifier',
            'RECTIFIER & BATTERY': 'Catu Daya & Rectifier',
            'RECTIFIER': 'Catu Daya & Rectifier',
        }.get(jenis_key, jenis_key.title())
        if sheet_name in created_sheets:
            # Tambah perangkat ke sheet yang sudah ada
            ws = wb[sheet_name]
            start_row = ws.max_row + 1
            for d in devices_jenis:
                ws[f'A{start_row}'] = d.nama
                ws[f'A{start_row}'].font = Font(bold=True,name='Arial',size=9)
                start_row += 1
        else:
            # Gabung devices Router + Switch
            if jenis_key in ('ROUTER', 'SWITCH'):
                devices_jenis = by_jenis.get('ROUTER',[]) + by_jenis.get('SWITCH',[])
            elif jenis_key in ('RECTIFIER','CATU DAYA','CATUDAYA','RECTIFIER & BATTERY'):
                devices_jenis = (by_jenis.get('RECTIFIER',[]) +
                                 by_jenis.get('CATU DAYA',[]) +
                                 by_jenis.get('CATUDAYA',[]) +
                                 by_jenis.get('RECTIFIER & BATTERY',[]))
            func(devices_jenis)
            created_sheets.add(sheet_name)

    # Sheet Corrective — semua perangkat di lokasi ini
    make_sheet_corrective(all_devices)

    # Sheet Referensi
    ws_ref = wb.create_sheet('Referensi Perangkat')
    ws_ref.sheet_properties.tabColor = '64748B'
    ref_cols = [('A','Nama Perangkat',30),('B','Jenis',20),('C','Lokasi',25),('D','IP Address',18)]
    style_header(ws_ref,1,ref_cols,'475569')
    ws_ref.freeze_panes='A2'
    for i,d in enumerate(all_devices,start=2):
        ws_ref[f'A{i}'] = d.nama
        ws_ref[f'B{i}'] = d.jenis.name if d.jenis else '—'
        ws_ref[f'C{i}'] = d.lokasi or '—'
        ws_ref[f'D{i}'] = d.ip_address or '—'

    # ── Response ─────────────────────────────────────────────────────
    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)

    response = HttpResponse(
        buffer.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    tgl = dj_timezone.localdate().strftime('%Y%m%d')
    lokasi_slug = selected_lokasi.replace(' ','_').upper() if selected_lokasi else 'SEMUA'
    response['Content-Disposition'] = f'attachment; filename="Template_Maintenance_{lokasi_slug}_{tgl}.xlsx"'
    return response


@login_required
@require_can_edit
def offline_form_upload(request):
    """Upload Excel template yang sudah diisi offline untuk import ke database."""
    from maintenance.models import MaintenanceCorrective
    from django.contrib import messages

    results = None

    if request.method == 'POST' and request.FILES.get('file'):
        import openpyxl
        f = request.FILES['file']
        try:
            wb = openpyxl.load_workbook(f, data_only=True)
        except Exception as e:
            messages.error(request, f'Gagal membaca file: {e}')
            return render(request, 'maintenance/offline_upload.html', {'results': None})

        imported = []
        errors = []
        row_num = 0

        # ── Import Corrective ──
        if 'Corrective' in wb.sheetnames:
            ws = wb['Corrective']
            for row in ws.iter_rows(min_row=4, max_col=11, values_only=False):
                row_num += 1
                vals = [c.value for c in row]
                nama_device = str(vals[0] or '').strip()
                tanggal_raw = vals[1]
                pelaksana_raw = str(vals[2] or '').strip()
                jenis = str(vals[3] or '').strip()
                deskripsi = str(vals[4] or '').strip()
                tindakan = str(vals[5] or '').strip()
                komponen_yn = str(vals[6] or '').strip().lower()
                nama_komp = str(vals[7] or '').strip()
                kondisi_sblm = str(vals[8] or '').strip()
                kondisi_ssdh = str(vals[9] or '').strip()
                status_raw = str(vals[10] or 'selesai').strip()

                if not nama_device:
                    continue

                device = Device.objects.filter(nama__iexact=nama_device, is_deleted=False).first()
                if not device:
                    errors.append(f'Baris {row_num + 3}: Perangkat "{nama_device}" tidak ditemukan')
                    continue

                # Parse tanggal
                try:
                    if isinstance(tanggal_raw, str):
                        from datetime import datetime
                        tanggal = datetime.strptime(tanggal_raw.strip(), '%Y-%m-%d %H:%M')
                    else:
                        tanggal = tanggal_raw
                    if not tanggal:
                        raise ValueError('Tanggal kosong')
                except Exception:
                    errors.append(f'Baris {row_num + 3}: Format tanggal tidak valid — gunakan YYYY-MM-DD HH:MM')
                    continue

                pelaksana_list = [n.strip() for n in pelaksana_raw.split(',') if n.strip()] if pelaksana_raw else []
                m_status = 'Done' if status_raw == 'selesai' else 'Open'
                komponen_diganti = komponen_yn in ('ya', 'yes', '1', 'true')

                maint = Maintenance.objects.create(
                    device=device,
                    maintenance_type='Corrective',
                    date=tanggal,
                    description=deskripsi,
                    status=m_status,
                    pelaksana_names=pelaksana_list,
                )
                MaintenanceCorrective.objects.create(
                    maintenance=maint,
                    jenis_kerusakan=jenis if jenis in ('hardware','software','power','komunikasi','mekanik','lainnya') else '',
                    deskripsi_masalah=deskripsi,
                    tindakan=tindakan,
                    komponen_diganti=komponen_diganti,
                    nama_komponen=nama_komp,
                    kondisi_sebelum=kondisi_sblm,
                    kondisi_sesudah=kondisi_ssdh,
                    status_perbaikan=status_raw if status_raw in ('selesai','perlu_tindaklanjut') else 'selesai',
                )

                if komponen_diganti and nama_komp:
                    from devices.models import DeviceEvent
                    tgl_str = str(tanggal)[:10] if tanggal else str(dj_timezone.localdate())
                    DeviceEvent.objects.create(
                        device=device,
                        tipe='penggantian',
                        tanggal=tgl_str,
                        komponen=nama_komp,
                        nilai_lama=kondisi_sblm,
                        nilai_baru=kondisi_ssdh,
                        catatan=f'Import offline — {deskripsi[:80]}',
                        dilakukan_oleh=request.user,
                    )

                imported.append(f'{device.nama} — {deskripsi[:50]}')

        # ── Helper parse tanggal ──────────────────────────────────────
        def parse_tanggal(raw):
            from datetime import datetime
            if isinstance(raw, str):
                for fmt in ('%Y-%m-%d %H:%M', '%Y-%m-%d %H:%M:%S', '%d/%m/%Y %H:%M', '%Y-%m-%d'):
                    try:
                        return datetime.strptime(raw.strip(), fmt)
                    except ValueError:
                        continue
                raise ValueError(f'Format tidak dikenali: {raw}')
            if raw is None:
                raise ValueError('Tanggal kosong')
            return raw

        def import_preventive_sheet(ws, sheet_name, min_row, col_count, save_detail_fn=None):
            for row in ws.iter_rows(min_row=min_row, max_col=col_count, values_only=False):
                vals = [c.value for c in row]
                nama_device = str(vals[0] or '').strip()
                tanggal_raw = vals[1]
                pelaksana_raw = str(vals[2] or '').strip() if len(vals) > 2 else ''
                deskripsi = str(vals[3] or '').strip() if len(vals) > 3 else ''

                if not nama_device:
                    continue

                device = Device.objects.filter(nama__iexact=nama_device, is_deleted=False).first()
                if not device:
                    errors.append(f'[{sheet_name}] Perangkat "{nama_device}" tidak ditemukan')
                    continue

                if not tanggal_raw:
                    errors.append(f'[{sheet_name}] {nama_device}: Tanggal wajib diisi')
                    continue

                try:
                    tanggal = parse_tanggal(tanggal_raw)
                except Exception:
                    errors.append(f'[{sheet_name}] {nama_device}: Format tanggal tidak valid — gunakan YYYY-MM-DD HH:MM')
                    continue

                pelaksana_list = [n.strip() for n in pelaksana_raw.split(',') if n.strip()] if pelaksana_raw else []

                maint = Maintenance.objects.create(
                    device=device,
                    maintenance_type='Preventive',
                    date=tanggal,
                    description=deskripsi,
                    status='Open',
                    pelaksana_names=pelaksana_list,
                )

                if save_detail_fn:
                    try:
                        save_detail_fn(maint, vals)
                    except Exception as e:
                        errors.append(f'[{sheet_name}] {nama_device}: Gagal simpan detail — {e}')

                imported.append(f'[{sheet_name}] {nama_device}')

        def _g(vals, idx, default=''):
            try:
                v = vals[idx]
                return v if v is not None else default
            except IndexError:
                return default

        def _gf(vals, idx):
            try:
                v = vals[idx]
                return float(v) if v not in (None, '') else None
            except (IndexError, ValueError, TypeError):
                return None

        def _gi(vals, idx):
            try:
                v = vals[idx]
                return int(v) if v not in (None, '') else None
            except (IndexError, ValueError, TypeError):
                return None

        if 'Router & Switch' in wb.sheetnames:
            def save_router(maint, vals):
                from maintenance.models import MaintenanceRouter
                MaintenanceRouter.objects.create(
                    maintenance=maint,
                    kondisi_fisik=str(_g(vals,4))[:3] or '',
                    led_link=str(_g(vals,5))[:3] or '',
                    kondisi_kabel=str(_g(vals,6))[:3] or '',
                    tegangan_input=_gf(vals,7), suhu_perangkat=_gf(vals,8),
                    cpu_load=_gf(vals,9), memory_usage=_gf(vals,10),
                    jumlah_port_aktif=_gi(vals,11), jumlah_port_total=_gi(vals,12),
                    status_routing=str(_g(vals,13))[:3] or '',
                    catatan_tambahan=str(_g(vals,14)),
                )
            import_preventive_sheet(wb['Router & Switch'], 'Router & Switch', 4, 15, save_router)

        if 'PLC' in wb.sheetnames:
            def save_plc(maint, vals):
                from maintenance.models import MaintenancePLC
                MaintenancePLC.objects.create(
                    maintenance=maint,
                    akses_plc=str(_g(vals,4))[:3] or '',
                    remote_akses_plc=str(_g(vals,5))[:3] or '',
                    transmission_line=_gf(vals,6), rx_pilot_level=_gf(vals,7),
                    freq_tx=_gf(vals,8), bandwidth_tx=_gf(vals,9),
                    freq_rx=_gf(vals,10), bandwidth_rx=_gf(vals,11),
                    time_sync=str(_g(vals,12))[:3] or '',
                    wave_trap=str(_g(vals,13))[:3] or '',
                    imu=str(_g(vals,14))[:3] or '',
                    kabel_coaxial=str(_g(vals,15))[:3] or '',
                )
            import_preventive_sheet(wb['PLC'], 'PLC', 4, 16, save_plc)

        if 'Radio' in wb.sheetnames:
            def save_radio(maint, vals):
                from maintenance.models import MaintenanceRadio
                MaintenanceRadio.objects.create(
                    maintenance=maint,
                    suhu_ruangan=_gf(vals,4),
                    kebersihan=str(_g(vals,5))[:10] or '',
                    lampu_penerangan=str(_g(vals,6))[:15] or '',
                    ada_radio=str(_g(vals,7))[:3] or '',
                    ada_battery=str(_g(vals,8))[:3] or '',
                    merk_battery=str(_g(vals,9)),
                    ada_power_supply=str(_g(vals,10))[:3] or '',
                    merk_power_supply=str(_g(vals,11)),
                    jenis_antena=str(_g(vals,12))[:15] or '',
                    swr=str(_g(vals,13))[:5] or '',
                    power_tx=_gf(vals,14), tegangan_battery=_gf(vals,15),
                    tegangan_psu=_gf(vals,16), frekuensi_tx=_gf(vals,17),
                    frekuensi_rx=_gf(vals,18), catatan=str(_g(vals,19)),
                )
            import_preventive_sheet(wb['Radio'], 'Radio', 4, 20, save_radio)

        if 'VoIP' in wb.sheetnames:
            def save_voip(maint, vals):
                from maintenance.models import MaintenanceVoIP
                MaintenanceVoIP.objects.create(
                    maintenance=maint,
                    ip_address=str(_g(vals,4)), extension_number=str(_g(vals,5)),
                    sip_server_1=str(_g(vals,6)), sip_server_2=str(_g(vals,7)),
                    suhu_ruangan=_gf(vals,8),
                    kondisi_fisik=str(_g(vals,9))[:3] or '',
                    ntp_server=str(_g(vals,10))[:3] or '',
                    webconfig=str(_g(vals,11))[:3] or '',
                    ps_merk=str(_g(vals,12)), ps_tegangan_input=_gf(vals,13),
                    ps_status=str(_g(vals,14))[:3] or '',
                    catatan=str(_g(vals,15)),
                )
            import_preventive_sheet(wb['VoIP'], 'VoIP', 4, 16, save_voip)

        if 'Multiplexer' in wb.sheetnames:
            def save_mux(maint, vals):
                from maintenance.models import MaintenanceMux
                MaintenanceMux.objects.create(
                    maintenance=maint,
                    suhu_ruangan=_gf(vals,4),
                    kebersihan=str(_g(vals,5))[:10] or '',
                    lampu_penerangan=str(_g(vals,6))[:15] or '',
                    brand=str(_g(vals,7)), firmware=str(_g(vals,8)),
                    sync_source_1=str(_g(vals,9)), sync_source_2=str(_g(vals,10)),
                    hs1_tx=_gf(vals,11), hs1_rx=_gf(vals,12), hs1_jarak=_gf(vals,13),
                    hs2_tx=_gf(vals,14), hs2_rx=_gf(vals,15), hs2_jarak=_gf(vals,16),
                    psu1_status=str(_g(vals,17))[:3] or '',
                    psu2_status=str(_g(vals,18))[:3] or '',
                    fan_status=str(_g(vals,19))[:3] or '',
                    catatan=str(_g(vals,20)),
                )
            import_preventive_sheet(wb['Multiplexer'], 'Multiplexer', 4, 21, save_mux)

        if 'Catu Daya & Rectifier' in wb.sheetnames:
            def save_rect(maint, vals):
                from maintenance.models import MaintenanceRectifier
                MaintenanceRectifier.objects.create(
                    maintenance=maint,
                    suhu_ruangan=_gf(vals,4),
                    exhaust_fan=str(_g(vals,5))[:20] or '',
                    kebersihan=str(_g(vals,6))[:10] or '',
                    lampu_penerangan=str(_g(vals,7))[:15] or '',
                    rect1_merk=str(_g(vals,8)), rect1_tipe=str(_g(vals,9)),
                    rect1_kondisi=str(_g(vals,10))[:3] or '',
                    rect1_v_rectifier=_gf(vals,11), rect1_v_battery=_gf(vals,12),
                    rect1_teg_pos_ground=_gf(vals,13), rect1_teg_neg_ground=_gf(vals,14),
                    rect1_v_dropper=_gf(vals,15), rect1_a_rectifier=_gf(vals,16),
                    rect1_a_battery=_gf(vals,17), rect1_a_load=_gf(vals,18),
                    bat1_merk=str(_g(vals,19)), bat1_tipe=str(_g(vals,20)),
                    bat1_kondisi=str(_g(vals,21))[:3] or '',
                    bat1_jumlah=_gi(vals,22), bat1_v_total=_gf(vals,23),
                    catatan=str(_g(vals,24)),
                )
            import_preventive_sheet(wb['Catu Daya & Rectifier'], 'Catu Daya & Rectifier', 4, 25, save_rect)

        if 'Teleproteksi' in wb.sheetnames:
            def save_tp(maint, vals):
                from maintenance.models import MaintenanceTeleproteksi
                MaintenanceTeleproteksi.objects.create(
                    maintenance=maint,
                    suhu_ruangan=_gf(vals,4),
                    kebersihan_perangkat=str(_g(vals,5))[:10] or '',
                    kebersihan_panel=str(_g(vals,6))[:10] or '',
                    lampu=str(_g(vals,7))[:3] or '',
                    link=str(_g(vals,8)), tipe_tp=str(_g(vals,9))[:10] or '',
                    port_comm=str(_g(vals,10))[:10] or '',
                    versi_program=str(_g(vals,11)), address_tp=str(_g(vals,12)),
                    akses_tp=str(_g(vals,13))[:3] or '',
                    remote_akses_tp=str(_g(vals,14))[:3] or '',
                    jumlah_skema=_gi(vals,15),
                    skema_1_command=str(_g(vals,16))[:20] or '',
                    skema_1_send_minus=_gf(vals,17), skema_1_send_plus=_gf(vals,18),
                    skema_1_receive_minus=_gf(vals,19), skema_1_receive_plus=_gf(vals,20),
                    skema_2_command=str(_g(vals,21))[:20] or '',
                    skema_2_send_minus=_gf(vals,22), skema_2_send_plus=_gf(vals,23),
                    skema_2_receive_minus=_gf(vals,24), skema_2_receive_plus=_gf(vals,25),
                    skema_3_command=str(_g(vals,26))[:20] or '',
                    skema_3_send_minus=_gf(vals,27), skema_3_send_plus=_gf(vals,28),
                    skema_3_receive_minus=_gf(vals,29), skema_3_receive_plus=_gf(vals,30),
                    skema_4_command=str(_g(vals,31))[:20] or '',
                    skema_4_send_minus=_gf(vals,32), skema_4_send_plus=_gf(vals,33),
                    skema_4_receive_minus=_gf(vals,34), skema_4_receive_plus=_gf(vals,35),
                    skema_1_send_result=str(_g(vals,36))[:3] or '',
                    skema_1_receive_result=str(_g(vals,37))[:3] or '',
                    skema_2_send_result=str(_g(vals,38))[:3] or '',
                    skema_2_receive_result=str(_g(vals,39))[:3] or '',
                    skema_3_send_result=str(_g(vals,40))[:3] or '',
                    skema_3_receive_result=str(_g(vals,41))[:3] or '',
                    skema_4_send_result=str(_g(vals,42))[:3] or '',
                    skema_4_receive_result=str(_g(vals,43))[:3] or '',
                    time_sync=str(_g(vals,44))[:3] or '',
                    loop_test=_gf(vals,45), catatan=str(_g(vals,46)),
                )
            import_preventive_sheet(wb['Teleproteksi'], 'Teleproteksi', 4, 47, save_tp)

        results = {
            'imported': imported,
            'errors': errors,
            'total_imported': len(imported),
            'total_errors': len(errors),
        }

        if imported:
            messages.success(request, f'Berhasil mengimport {len(imported)} data maintenance.')
        if errors:
            messages.warning(request, f'Ada {len(errors)} baris yang gagal diimport.')

    lokasi_list = Device.objects.filter(is_deleted=False).exclude(
        lokasi__isnull=True).exclude(lokasi='').values_list(
        'lokasi', flat=True).distinct().order_by('lokasi')

    return render(request, 'maintenance/offline_upload.html', {
        'results': results,
        'lokasi_list': lokasi_list,
    })