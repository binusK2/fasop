from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import Device, Icon, DeviceType
from .forms import DeviceForm, IconForm
from django.db.models import Count, Q
from django.db.models.functions import TruncMonth, Lower, Trim
from maintenance.models import Maintenance
from django.utils.timezone import now
from django.http import HttpResponse
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter


@login_required
def device_list(request):
    jenis_id = request.GET.get('jenis')
    search = request.GET.get('q') or ''
    lokasi = request.GET.get('lokasi')
    devices = Device.objects.filter(is_deleted=False)

    if jenis_id:
        devices = devices.filter(jenis_id=jenis_id)

    if search:
        devices = devices.filter(
            Q(nama__icontains=search) |
            Q(ip_address__icontains=search)
        )

    if lokasi:
        devices = devices.filter(lokasi=lokasi)

    lokasi_list = (
        Device.objects
        .filter(is_deleted=False)
        .exclude(lokasi__isnull=True)
        .exclude(lokasi__exact='')
        .exclude(lokasi__iexact='none')
        .annotate(lokasi_clean=Trim('lokasi'))
        .values_list('lokasi_clean', flat=True)
        .distinct()
        .order_by('lokasi_clean')
    )

    return render(request, 'devices/device_list.html', {
        'devices': devices,
        'search': search,
        'selected_jenis': jenis_id,
        'lokasi_list': lokasi_list,
        'selected_lokasi': lokasi,
    })


@login_required
def device_create(request):
    if request.method == 'POST':
        form = DeviceForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            return redirect('device_list')
    else:
        form = DeviceForm()
    return render(request, 'devices/device_form.html', {'form': form, 'is_edit': False})


@login_required
def device_update(request, pk):
    device = get_object_or_404(Device, pk=pk)
    if request.method == 'POST':
        form = DeviceForm(request.POST, request.FILES, instance=device)
        if form.is_valid():
            form.save()
            return redirect('device_view', pk=device.pk)
    else:
        form = DeviceForm(instance=device)
    return render(request, 'devices/device_form.html', {'form': form, 'is_edit': True, 'device': device})


@login_required
def device_delete(request, pk):
    device = get_object_or_404(Device, pk=pk)
    device.is_deleted = True
    device.deleted_by = request.user
    device.save()
    return redirect('device_list')


@login_required
def dashboard(request):
    total_devices = Device.objects.filter(is_deleted=False).count()

    # Hitung per jenis + persen untuk progress bar
    device_by_type_qs = (
        Device.objects
        .filter(is_deleted=False)
        .values('jenis__name', 'jenis__id')
        .annotate(total=Count('id'))
        .order_by('jenis__name')
    )

    # tambah pct untuk progress bar
    device_by_type = []
    for d in device_by_type_qs:
        pct = round((d['total'] / total_devices * 100)) if total_devices else 0
        device_by_type.append({**d, 'pct': pct})

    total_maintenance = Maintenance.objects.count()
    maintenance_open = Maintenance.objects.filter(status='Open').count()
    maintenance_done = Maintenance.objects.filter(status='Done').count()
    belum_ttd = Maintenance.objects.filter(status='Done', signed_by__isnull=True).count()

    maintenance_by_month = (
        Maintenance.objects
        .annotate(month=TruncMonth('date'))
        .values('month')
        .annotate(total=Count('id'))
        .order_by('month')
    )

    # Maintenance open terbaru (5 record)
    recent_open_maintenance = (
        Maintenance.objects
        .filter(status='Open')
        .select_related('device')
        .order_by('-date')[:5]
    )

    return render(request, 'devices/dashboard.html', {
        'total_devices': total_devices,
        'device_by_type': device_by_type,
        'total_maintenance': total_maintenance,
        'maintenance_open': maintenance_open,
        'maintenance_done': maintenance_done,
        'belum_ttd': belum_ttd,
        'maintenance_by_month': maintenance_by_month,
        'recent_open_maintenance': recent_open_maintenance,
    })


@login_required
def device_detail(request, pk):
    device = get_object_or_404(Device, pk=pk)
    maintenance_history = Maintenance.objects.filter(device=device).order_by('-date')
    maintenance_total = maintenance_history.count()
    maintenance_done = maintenance_history.filter(status='Done').count()
    maintenance_open = maintenance_history.filter(status='Open').count()

    return render(request, 'devices/device_detail.html', {
        'device': device,
        'maintenance_history': maintenance_history,
        'maintenance_total': maintenance_total,
        'maintenance_done': maintenance_done,
        'maintenance_open': maintenance_open,
    })


@login_required
def device_by_type(request, type_id):
    devices = Device.objects.filter(jenis_id=type_id, is_deleted=False)
    device_type = get_object_or_404(DeviceType, id=type_id)
    lokasi_list = (
        Device.objects.filter(is_deleted=False)
        .exclude(lokasi__isnull=True).exclude(lokasi__exact='')
        .annotate(lokasi_clean=Trim('lokasi'))
        .values_list('lokasi_clean', flat=True)
        .distinct().order_by('lokasi_clean')
    )
    return render(request, 'devices/device_list.html', {
        'devices': devices,
        'filter_type': device_type,
        'lokasi_list': lokasi_list,
        'selected_jenis': type_id,
    })


@login_required
def lokasi_list(request):
    lokasi_data = (
        Device.objects
        .filter(is_deleted=False)
        .exclude(lokasi__isnull=True)
        .exclude(lokasi__exact='')
        .exclude(lokasi__iexact='none')
        .annotate(lokasi_clean=Trim('lokasi'))
        .values('lokasi_clean')
        .annotate(total_device=Count('id'))
        .order_by('lokasi_clean')
    )
    # Tambahkan info maintenance open per lokasi
    from maintenance.models import Maintenance
    open_by_lokasi = {}
    for m in Maintenance.objects.filter(status='Open').select_related('device'):
        loc = (m.device.lokasi or '').strip()
        open_by_lokasi[loc] = open_by_lokasi.get(loc, 0) + 1

    lokasi_list_final = []
    for row in lokasi_data:
        row = dict(row)
        row['maintenance_open'] = open_by_lokasi.get(row['lokasi_clean'], 0)
        lokasi_list_final.append(row)

    return render(request, 'devices/lokasi_list.html', {'lokasi_data': lokasi_list_final})


@login_required
def layanan_icon(request):
    icons = Icon.objects.all()

    # Filter
    search = request.GET.get('q', '').strip()
    selected_kondisi = request.GET.get('kondisi', '').strip()

    if search:
        icons = icons.filter(
            Q(name__icontains=search) |
            Q(lokasi_layanan__icontains=search) |
            Q(SID1__icontains=search) |
            Q(SID2__icontains=search) |
            Q(keterangan__icontains=search)
        )
    if selected_kondisi:
        icons = icons.filter(kondisi_operasional__icontains=selected_kondisi)

    icons = list(icons)

    # Summary counters
    operasi_baik     = sum(1 for i in icons if i.kondisi_operasional and 'Baik' in i.kondisi_operasional)
    operasi_gangguan = sum(1 for i in icons if i.kondisi_operasional and ('Gangguan' in i.kondisi_operasional or 'NOK' in i.kondisi_operasional))
    operasi_lain     = len(icons) - operasi_baik - operasi_gangguan

    # Distinct kondisi values for filter dropdown
    kondisi_list = sorted(set(
        i.kondisi_operasional for i in Icon.objects.all()
        if i.kondisi_operasional
    ))

    return render(request, 'devices/layanan_icon.html', {
        'icons':            icons,
        'search':           search,
        'selected_kondisi': selected_kondisi,
        'kondisi_list':     kondisi_list,
        'operasi_baik':     operasi_baik,
        'operasi_gangguan': operasi_gangguan,
        'operasi_lain':     operasi_lain,
    })


@login_required
def icon_create(request):
    if request.method == 'POST':
        form = IconForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            return redirect('layanan_icon')
    else:
        form = IconForm()
    return render(request, 'devices/icon_form.html', {
        'form': form,
        'is_edit': False,
        'kondisi_choices': [('Operasi Baik','Operasi Baik'),('Gangguan','Gangguan'),('Tidak Operasi','Tidak Operasi'),('Dalam Pemeliharaan','Dalam Pemeliharaan')],
    })


@login_required
def icon_update(request, pk):
    icon = get_object_or_404(Icon, pk=pk)
    if request.method == 'POST':
        form = IconForm(request.POST, request.FILES, instance=icon)
        if form.is_valid():
            form.save()
            return redirect('layanan_icon')
    else:
        form = IconForm(instance=icon)
    return render(request, 'devices/icon_form.html', {
        'form': form,
        'is_edit': True,
        'icon': icon,
        'kondisi_choices': [('Operasi Baik','Operasi Baik'),('Gangguan','Gangguan'),('Tidak Operasi','Tidak Operasi'),('Dalam Pemeliharaan','Dalam Pemeliharaan')],
    })


@login_required
def icon_delete(request, pk):
    icon = get_object_or_404(Icon, pk=pk)
    if request.method == 'POST':
        icon.delete()
    return redirect('layanan_icon')


# =====================================================
# QR CODE VIEW — buka halaman print QR
# =====================================================
@login_required
def device_qr(request, pk):
    device = get_object_or_404(Device, pk=pk)
    detail_url = request.build_absolute_uri(f'/view/{pk}/')
    return render(request, 'devices/device_qr.html', {
        'device': device,
        'detail_url': detail_url,
    })


# =====================================================
# EXPORT DEVICES KE EXCEL
# =====================================================
@login_required
def export_devices_excel(request):
    jenis_id = request.GET.get('jenis')
    search = request.GET.get('q') or ''
    lokasi = request.GET.get('lokasi')

    devices = Device.objects.filter(is_deleted=False).select_related('jenis')

    if jenis_id:
        devices = devices.filter(jenis_id=jenis_id)
    if search:
        devices = devices.filter(Q(nama__icontains=search) | Q(ip_address__icontains=search))
    if lokasi:
        devices = devices.filter(lokasi=lokasi)

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Inventory Peralatan"

    # Styles
    header_fill = PatternFill("solid", fgColor="0F172A")
    header_font = Font(bold=True, color="FFFFFF", size=11)
    header_align = Alignment(horizontal="center", vertical="center", wrap_text=True)
    center_align = Alignment(horizontal="center", vertical="center")
    thin_border = Border(
        left=Side(style='thin'), right=Side(style='thin'),
        top=Side(style='thin'), bottom=Side(style='thin')
    )

    # Judul
    ws.merge_cells('A1:I1')
    title_cell = ws['A1']
    title_cell.value = "INVENTORY PERALATAN FASOP UP2B"
    title_cell.font = Font(bold=True, size=13)
    title_cell.alignment = Alignment(horizontal="center", vertical="center")
    title_cell.fill = PatternFill("solid", fgColor="EFF6FF")
    ws.row_dimensions[1].height = 28

    ws.merge_cells('A2:I2')
    from datetime import date
    ws['A2'].value = f"Dicetak: {date.today().strftime('%d %B %Y')}"
    ws['A2'].alignment = Alignment(horizontal="center")
    ws['A2'].font = Font(size=10, italic=True, color="64748B")
    ws.row_dimensions[2].height = 18

    ws.row_dimensions[3].height = 6  # spacer

    # Header
    headers = ['No', 'Nama', 'Jenis', 'Merk', 'Type/Model', 'Serial Number', 'IP Address', 'Lokasi', 'Firmware']
    col_widths = [5, 25, 15, 15, 18, 20, 16, 20, 15]

    for col_idx, (header, width) in enumerate(zip(headers, col_widths), 1):
        cell = ws.cell(row=4, column=col_idx, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_align
        cell.border = thin_border
        ws.column_dimensions[get_column_letter(col_idx)].width = width

    ws.row_dimensions[4].height = 22

    # Data
    alt_fill = PatternFill("solid", fgColor="F8FAFC")
    for row_idx, d in enumerate(devices, 1):
        ws_row = row_idx + 4
        row_data = [
            row_idx,
            d.nama,
            d.jenis.name if d.jenis else '-',
            d.merk,
            d.type or '-',
            d.serial_number or '-',
            str(d.ip_address),
            d.lokasi,
            d.firmware_version or '-',
        ]
        for col_idx, value in enumerate(row_data, 1):
            cell = ws.cell(row=ws_row, column=col_idx, value=value)
            cell.border = thin_border
            cell.alignment = center_align if col_idx == 1 else Alignment(vertical="center")
            if row_idx % 2 == 0:
                cell.fill = alt_fill
        ws.row_dimensions[ws_row].height = 18

    # Freeze panes
    ws.freeze_panes = 'A5'

    # Response
    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = 'attachment; filename="inventory_peralatan_fasop.xlsx"'
    wb.save(response)
    return response


@login_required
def export_icon_excel(request):
    from datetime import date

    icons = Icon.objects.all()

    # Apply same filters as list view
    search = request.GET.get('q', '').strip()
    selected_kondisi = request.GET.get('kondisi', '').strip()
    if search:
        icons = icons.filter(
            Q(name__icontains=search) |
            Q(lokasi_layanan__icontains=search) |
            Q(SID1__icontains=search) |
            Q(SID2__icontains=search) |
            Q(keterangan__icontains=search)
        )
    if selected_kondisi:
        icons = icons.filter(kondisi_operasional__icontains=selected_kondisi)

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Layanan ICON+"

    # Styles
    header_fill  = PatternFill("solid", fgColor="0F172A")
    header_font  = Font(bold=True, color="FFFFFF", size=11)
    header_align = Alignment(horizontal="center", vertical="center", wrap_text=True)
    center_align = Alignment(horizontal="center", vertical="center")
    left_align   = Alignment(horizontal="left", vertical="center", wrap_text=True)
    thin_border  = Border(
        left=Side(style='thin'), right=Side(style='thin'),
        top=Side(style='thin'),  bottom=Side(style='thin')
    )
    alt_fill = PatternFill("solid", fgColor="F8FAFC")

    COLS = 9

    # Judul
    ws.merge_cells(f'A1:{get_column_letter(COLS)}1')
    ws['A1'].value     = "DATA LAYANAN ICON+ — FASOP UP2B"
    ws['A1'].font      = Font(bold=True, size=13)
    ws['A1'].alignment = Alignment(horizontal="center", vertical="center")
    ws['A1'].fill      = PatternFill("solid", fgColor="EFF6FF")
    ws.row_dimensions[1].height = 28

    ws.merge_cells(f'A2:{get_column_letter(COLS)}2')
    ws['A2'].value     = f"Dicetak: {date.today().strftime('%d %B %Y')}"
    ws['A2'].alignment = Alignment(horizontal="center")
    ws['A2'].font      = Font(size=10, italic=True, color="64748B")
    ws.row_dimensions[2].height = 18
    ws.row_dimensions[3].height = 6  # spacer

    # Header row
    headers    = ['No', 'Nama Layanan', 'Lokasi Layanan', 'Bandwidth', 'SID 1', 'SID 2', 'Kontrak', 'Kondisi Operasional', 'Keterangan']
    col_widths = [5,    28,             25,                14,          22,      22,      18,        22,                   35]

    for col_idx, (h, w) in enumerate(zip(headers, col_widths), 1):
        cell = ws.cell(row=4, column=col_idx, value=h)
        cell.font      = header_font
        cell.fill      = header_fill
        cell.alignment = header_align
        cell.border    = thin_border
        ws.column_dimensions[get_column_letter(col_idx)].width = w
    ws.row_dimensions[4].height = 22

    # Conditional fill colours for kondisi
    green_fill  = PatternFill("solid", fgColor="DCFCE7")
    red_fill    = PatternFill("solid", fgColor="FEE2E2")
    yellow_fill = PatternFill("solid", fgColor="FEF3C7")

    # Data rows
    for row_idx, d in enumerate(icons, 1):
        ws_row = row_idx + 4
        row_data = [
            row_idx,
            d.name or '-',
            d.lokasi_layanan or '-',
            d.bandwidth or '-',
            d.SID1 or '-',
            d.SID2 or '-',
            d.kontrak or '-',
            d.kondisi_operasional or '-',
            d.keterangan or '-',
        ]
        for col_idx, value in enumerate(row_data, 1):
            cell            = ws.cell(row=ws_row, column=col_idx, value=value)
            cell.border     = thin_border
            cell.alignment  = center_align if col_idx == 1 else left_align
            if row_idx % 2 == 0:
                cell.fill = alt_fill

        # Colour-code kondisi cell (col 8)
        kondisi_val = d.kondisi_operasional or ''
        kondisi_cell = ws.cell(row=ws_row, column=8)
        if 'Baik' in kondisi_val:
            kondisi_cell.fill = green_fill
            kondisi_cell.font = Font(bold=True, color="065F46")
        elif 'Gangguan' in kondisi_val or 'NOK' in kondisi_val:
            kondisi_cell.fill = red_fill
            kondisi_cell.font = Font(bold=True, color="991B1B")
        elif kondisi_val != '-':
            kondisi_cell.fill = yellow_fill
            kondisi_cell.font = Font(bold=True, color="92400E")

        ws.row_dimensions[ws_row].height = 18

    # Freeze header
    ws.freeze_panes = 'A5'

    # Auto-filter
    ws.auto_filter.ref = f'A4:{get_column_letter(COLS)}{4 + icons.count() if hasattr(icons, "count") else 4 + len(list(icons))}'

    # Response
    from django.http import HttpResponse
    import io
    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    filename = f"layanan_icon_{date.today().strftime('%Y%m%d')}.xlsx"
    response = HttpResponse(
        buffer.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response
