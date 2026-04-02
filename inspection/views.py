from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.utils import timezone
from django.db.models import Count, Q
from .models import Inspection, InspectionCatuDaya, InspectionDefenseScheme
from devices.models import Device, DeviceType, SiteLocation
from datetime import date
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter


# ── Jenis perangkat yang bisa diinspeksi ────────────────────────────
INSPECTABLE_JENIS = {
    'Catu Daya':          'catu_daya',
    'RELE DEFENSE SCHEME': 'defense_scheme',
}


def require_operator(view_func):
    """Decorator: hanya operator, AM, superuser yang boleh akses."""
    from functools import wraps
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            from django.contrib.auth.views import redirect_to_login
            return redirect_to_login(request.get_full_path())
        if request.user.is_superuser:
            return view_func(request, *args, **kwargs)
        try:
            role = request.user.profile.role
        except Exception:
            role = ''
        if role in ('operator', 'technician', 'asisten_manager'):
            return view_func(request, *args, **kwargs)
        from django.shortcuts import render
        return render(request, '403.html',
                      {'message': 'Halaman ini hanya untuk Operator.'}, status=403)
    return wrapper


# ─────────────────────────────────────────────────────────────────────
# PILIH LOKASI
# ─────────────────────────────────────────────────────────────────────
@login_required
@require_operator
def inspection_lokasi(request):
    """Halaman utama — pilih lokasi GI untuk inspeksi."""
    jenis_names = list(INSPECTABLE_JENIS.keys())
    lokasi_qs = (
        Device.objects
        .filter(is_deleted=False, jenis__name__in=jenis_names)
        .exclude(lokasi__isnull=True).exclude(lokasi='')
        .values_list('lokasi', flat=True)
        .distinct().order_by('lokasi')
    )

    today = date.today()
    lokasi_stats = []
    for lok in lokasi_qs:
        insp_today = Inspection.objects.filter(
            device__lokasi=lok,
            tanggal__date=today,
        ).count()
        total_device = Device.objects.filter(
            is_deleted=False, jenis__name__in=jenis_names, lokasi=lok
        ).count()
        lokasi_stats.append({
            'lokasi': lok,
            'today':  insp_today,
            'total':  total_device,
        })

    return render(request, 'inspection/lokasi.html', {
        'lokasi_stats': lokasi_stats,
        'today':        today,
    })


# ─────────────────────────────────────────────────────────────────────
# DAFTAR PERANGKAT DI LOKASI
# ─────────────────────────────────────────────────────────────────────
@login_required
@require_operator
def inspection_device_list(request, lokasi):
    """Daftar perangkat inspectable di lokasi tertentu."""
    jenis_names = list(INSPECTABLE_JENIS.keys())
    devices = (
        Device.objects
        .filter(is_deleted=False, jenis__name__in=jenis_names, lokasi=lokasi)
        .select_related('jenis')
        .order_by('jenis__name', 'nama')
    )

    # Build list of dict agar template tidak perlu filter gymnastics
    device_items = []
    for d in devices:
        last_insp = (
            Inspection.objects
            .filter(device=d)
            .select_related('operator')
            .order_by('-tanggal')
            .first()
        )
        device_items.append({
            'device':    d,
            'last_insp': last_insp,
        })

    return render(request, 'inspection/device_list.html', {
        'lokasi':       lokasi,
        'devices':      devices,
        'device_items': device_items,
    })


# ─────────────────────────────────────────────────────────────────────
# FORM INSPEKSI
# ─────────────────────────────────────────────────────────────────────
@login_required
@require_operator
def inspection_form(request, device_pk):
    """Form input inspeksi inservice."""
    device = get_object_or_404(Device, pk=device_pk, is_deleted=False)
    jenis_name = device.jenis.name.strip() if device.jenis else ''
    jenis_key  = INSPECTABLE_JENIS.get(jenis_name)

    if not jenis_key:
        return render(request, '403.html',
                      {'message': f'Perangkat jenis "{jenis_name}" belum didukung untuk inspeksi.'})

    if request.method == 'POST':
        # ── Simpan Inspection induk ──────────────────────────────────
        insp = Inspection.objects.create(
            device   = device,
            jenis    = jenis_key,
            tanggal  = timezone.now(),
            operator = request.user,
            catatan  = request.POST.get('catatan', '').strip(),
        )
        # Handle foto
        if request.FILES.get('foto'):
            insp.foto = request.FILES['foto']
            insp.save()

        # ── Simpan detail per jenis ──────────────────────────────────
        def g(key, default=''):
            return request.POST.get(key, default).strip()
        def gf(key):
            try:
                v = request.POST.get(key, '').strip()
                return float(v) if v else None
            except (ValueError, TypeError):
                return None

        if jenis_key == 'catu_daya':
            InspectionCatuDaya.objects.create(
                inspection              = insp,
                kondisi_rectifier       = g('kondisi_rectifier'),
                catatan_rectifier       = g('catatan_rectifier'),
                mode_recti              = g('mode_recti'),
                alarm_ground_fault      = g('alarm_ground_fault'),
                alarm_min_ac_fault      = g('alarm_min_ac_fault'),
                alarm_recti_fault       = g('alarm_recti_fault'),
                kebersihan_ruangan      = g('kebersihan_ruangan'),
                kondisi_baterai         = g('kondisi_baterai'),
                catatan_baterai         = g('catatan_baterai'),
                level_air_bank          = g('level_air_bank'),
                kebersihan_ruangan_bank = g('kebersihan_ruangan_bank'),
                kebersihan_bank         = g('kebersihan_bank'),
                exhaust_fan             = g('exhaust_fan'),
                tegangan_input_ac       = gf('tegangan_input_ac'),
                arus_input_ac           = gf('arus_input_ac'),
                tegangan_load_dc        = gf('tegangan_load_dc'),
                arus_load_dc            = gf('arus_load_dc'),
                tegangan_baterai_dc     = gf('tegangan_baterai_dc'),
                arus_baterai_dc         = gf('arus_baterai_dc'),
                kondisi_keseluruhan     = g('kondisi_keseluruhan'),
            )

        elif jenis_key == 'defense_scheme':
            InspectionDefenseScheme.objects.create(
                inspection     = insp,
                kondisi_relay  = g('kondisi_relay'),
                catatan_relay  = g('catatan_relay'),
                indikator_led  = g('indikator_led'),
                catatan_led    = g('catatan_led'),
                sumber_dc      = gf('sumber_dc'),
            )

        # ── Notifikasi ke AM jika ada kondisi Alarm/Tidak Normal ─────
        _kirim_notif_jika_perlu(insp, jenis_key, request.POST)

        return redirect('inspection_device_list', lokasi=device.lokasi)

    # GET — tampilkan form
    return render(request, 'inspection/form.html', {
        'device':    device,
        'jenis_key': jenis_key,
        'jenis_label': dict(Inspection.JENIS_CHOICES).get(jenis_key, ''),
    })


def _kirim_notif_jika_perlu(insp, jenis_key, post_data):
    """Kirim notifikasi ke AM jika ada kondisi alarm/tidak normal."""
    perlu_notif = False
    pesan_detail = []

    if jenis_key == 'catu_daya':
        if post_data.get('kondisi_rectifier') == 'alarm':
            perlu_notif = True
            pesan_detail.append('Rectifier: ALARM')
        if post_data.get('kondisi_keseluruhan') == 'kotor':
            perlu_notif = True
            pesan_detail.append('Kondisi keseluruhan: KOTOR')

    elif jenis_key == 'defense_scheme':
        if post_data.get('kondisi_relay') == 'alarm':
            perlu_notif = True
            pesan_detail.append('Kondisi Relay: ALARM')
        if post_data.get('indikator_led') == 'tidak_normal':
            perlu_notif = True
            pesan_detail.append('Indikator LED/Alarm: TIDAK NORMAL')

    if not perlu_notif:
        return

    try:
        from notifikasi.views import notif_ke_am
        notif_ke_am(
            tipe   = 'inspection_alert',
            judul  = f'Inspeksi Alert — {insp.device.nama}',
            pesan  = (
                f'Inspeksi inservice pada {insp.device.nama} ({insp.device.lokasi}) '
                f'tanggal {insp.tanggal.strftime("%d %b %Y %H:%M")} '
                f'mendeteksi kondisi: {", ".join(pesan_detail)}'
            ),
            level  = 'warning',
            url    = f'/inspection/riwayat/{insp.pk}/',
            device = insp.device,
        )
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────────────
# RIWAYAT INSPEKSI
# ─────────────────────────────────────────────────────────────────────
@login_required
@require_operator
def inspection_riwayat(request, pk):
    """Detail riwayat satu inspeksi."""
    insp = get_object_or_404(Inspection, pk=pk)
    detail = None
    detail_rows = []
    rectifier_rows = []
    bank_rows = []

    def mk_row(label, val, ok_val, ok_display, nok_display=None, alarm=False):
        is_ok = (val == ok_val)
        display = ok_display if is_ok else (nok_display or val or '—')
        bg = '#fee2e2' if (not is_ok and alarm) else '#fef9c3'
        fg = '#991b1b' if (not is_ok and alarm) else '#854d0e'
        prefix = '⚠ ' if (not is_ok and alarm and val) else ''
        return {'label': label, 'val': val, 'ok': is_ok,
                'display': prefix + display if val else '—',
                'bg': bg, 'fg': fg}

    try:
        if insp.jenis == 'catu_daya':
            detail = insp.detail_catu_daya
            detail_rows = [
                ('Teg. Input AC',   detail.tegangan_input_ac,   'V'),
                ('Arus Input AC',   detail.arus_input_ac,       'A'),
                ('Teg. Load DC',    detail.tegangan_load_dc,    'V'),
                ('Arus Load DC',    detail.arus_load_dc,        'A'),
                ('Teg. Baterai DC', detail.tegangan_baterai_dc, 'V'),
                ('Arus Baterai DC', detail.arus_baterai_dc,     'A'),
            ]
            rectifier_rows = [
                mk_row('Kondisi Rectifier', detail.kondisi_rectifier,
                       'normal', 'Normal', 'Alarm', alarm=True),
                mk_row('Mode Rectifier', detail.mode_recti,
                       'float', detail.get_mode_recti_display() if detail.mode_recti else ''),
                mk_row('Alarm Ground Fault', detail.alarm_ground_fault,
                       'tidak_ada', 'Tidak Ada', 'Ada', alarm=True),
                mk_row('Alarm Min AC Fault', detail.alarm_min_ac_fault,
                       'tidak_ada', 'Tidak Ada', 'Ada', alarm=True),
                mk_row('Alarm Recti Fault', detail.alarm_recti_fault,
                       'tidak_ada', 'Tidak Ada', 'Ada', alarm=True),
                mk_row('Kebersihan Ruangan', detail.kebersihan_ruangan,
                       'bersih', 'Bersih', 'Kotor'),
            ]
            bank_rows = [
                mk_row('Level Air Bank', detail.level_air_bank,
                       'normal', 'Normal',
                       detail.get_level_air_bank_display() if detail.level_air_bank else '—'),
                mk_row('Kebersihan Ruangan Bank', detail.kebersihan_ruangan_bank,
                       'bersih', 'Bersih', 'Kotor'),
                mk_row('Kebersihan Bank', detail.kebersihan_bank,
                       'bersih', 'Bersih', 'Kotor'),
                mk_row('Exhaust Fan', detail.exhaust_fan,
                       'nyala', 'Nyala', 'Mati', alarm=True),
                mk_row('Kondisi Baterai', detail.kondisi_baterai,
                       'bersih', 'Bersih', 'Kotor'),
            ]
        elif insp.jenis == 'defense_scheme':
            detail = insp.detail_defense_scheme
    except Exception:
        pass

    return render(request, 'inspection/riwayat_detail.html', {
        'insp':           insp,
        'detail':         detail,
        'detail_rows':    detail_rows,
        'rectifier_rows': rectifier_rows,
        'bank_rows':      bank_rows,
    })


@login_required
@require_operator
def inspection_riwayat_device(request, device_pk):
    """Riwayat semua inspeksi untuk satu device."""
    device = get_object_or_404(Device, pk=device_pk, is_deleted=False)
    inspeksi_qs = Inspection.objects.filter(device=device).order_by('-tanggal')

    # Tambah status_kondisi ke tiap inspeksi untuk template
    inspeksi_list = []
    for insp in inspeksi_qs:
        status = 'normal'
        try:
            if insp.jenis == 'catu_daya':
                d = insp.detail_catu_daya
                if d.kondisi_rectifier == 'alarm':
                    status = 'alarm'
            elif insp.jenis == 'defense_scheme':
                d = insp.detail_defense_scheme
                if d.kondisi_relay == 'alarm' or d.indikator_led == 'tidak_normal':
                    status = 'alarm'
        except Exception:
            pass
        insp.status_kondisi = status
        inspeksi_list.append(insp)

    return render(request, 'inspection/riwayat_device.html', {
        'device':        device,
        'inspeksi_list': inspeksi_list,
    })


# ─────────────────────────────────────────────────────────────────────
# EXPORT LAPORAN EXCEL
# ─────────────────────────────────────────────────────────────────────
@login_required
@require_operator
def inspection_export(request):
    """Export laporan inspeksi ke Excel."""
    lokasi    = request.GET.get('lokasi', '')
    jenis     = request.GET.get('jenis', '')
    date_from = request.GET.get('date_from', '')
    date_to   = request.GET.get('date_to', '')

    qs = Inspection.objects.select_related(
        'device', 'device__jenis', 'operator'
    ).order_by('-tanggal')

    if lokasi:    qs = qs.filter(device__lokasi=lokasi)
    if jenis:     qs = qs.filter(jenis=jenis)
    if date_from: qs = qs.filter(tanggal__date__gte=date_from)
    if date_to:   qs = qs.filter(tanggal__date__lte=date_to)

    wb  = openpyxl.Workbook()
    ws  = wb.active
    ws.title = 'Laporan Inspeksi'

    hdr_fill = PatternFill('solid', fgColor='0F172A')
    hdr_font = Font(bold=True, color='FFFFFF', size=10)
    hdr_aln  = Alignment(horizontal='center', vertical='center', wrap_text=True)
    c_aln    = Alignment(horizontal='center', vertical='center')
    l_aln    = Alignment(vertical='center', wrap_text=True)
    thin     = Side(style='thin')
    brd      = Border(left=thin, right=thin, top=thin, bottom=thin)
    alt_fill = PatternFill('solid', fgColor='F8FAFC')

    # Title
    ws.merge_cells('A1:J1')
    ws['A1'].value = 'LAPORAN INSPEKSI INSERVICE — FASOP UP2B MAKASSAR'
    ws['A1'].font  = Font(bold=True, size=12)
    ws['A1'].alignment = Alignment(horizontal='center', vertical='center')
    ws['A1'].fill  = PatternFill('solid', fgColor='EFF6FF')
    ws.row_dimensions[1].height = 26

    ws.merge_cells('A2:J2')
    ws['A2'].value = f"Dicetak: {date.today().strftime('%d %B %Y')}"
    ws['A2'].font  = Font(size=10, italic=True, color='64748B')
    ws['A2'].alignment = Alignment(horizontal='center')

    headers = ['No','Tanggal','Perangkat','Lokasi','Jenis','Operator',
               'Kondisi Utama','Nilai Utama','Status','Catatan']
    widths  = [5, 14, 25, 20, 20, 18, 18, 18, 14, 30]

    for ci, (h, w) in enumerate(zip(headers, widths), 1):
        cell = ws.cell(row=4, column=ci, value=h)
        cell.font = hdr_font; cell.fill = hdr_fill
        cell.alignment = hdr_aln; cell.border = brd
        ws.column_dimensions[get_column_letter(ci)].width = w
    ws.row_dimensions[4].height = 20
    ws.freeze_panes = 'A5'

    for ri, insp in enumerate(qs, 1):
        wr = ri + 4
        # Ambil kondisi dan nilai utama berdasarkan jenis
        kondisi_utama = nilai_utama = status = ''
        try:
            if insp.jenis == 'catu_daya':
                d = insp.detail_catu_daya
                kondisi_utama = d.get_kondisi_rectifier_display() if d.kondisi_rectifier else '—'
                nilai_utama   = f"Vload: {d.tegangan_load_dc or '—'} V"
                status        = 'ALARM' if d.kondisi_rectifier == 'alarm' else 'Normal'
            elif insp.jenis == 'defense_scheme':
                d = insp.detail_defense_scheme
                kondisi_utama = d.get_kondisi_relay_display() if d.kondisi_relay else '—'
                nilai_utama   = f"DC: {d.sumber_dc or '—'} V"
                status        = 'ALARM' if d.kondisi_relay == 'alarm' else \
                                ('Tidak Normal' if d.indikator_led == 'tidak_normal' else 'Normal')
        except Exception:
            kondisi_utama = nilai_utama = status = '—'

        op_name = insp.operator.get_full_name() or insp.operator.username if insp.operator else '—'
        row_data = [
            ri,
            insp.tanggal.strftime('%d/%m/%Y %H:%M'),
            str(insp.device),
            insp.device.lokasi or '—',
            insp.get_jenis_display(),
            op_name,
            kondisi_utama,
            nilai_utama,
            status,
            insp.catatan or '—',
        ]
        for ci, val in enumerate(row_data, 1):
            cell = ws.cell(row=wr, column=ci, value=val)
            cell.border    = brd
            cell.alignment = c_aln if ci in [1,2,9] else l_aln
            if ci == 9 and status in ('ALARM', 'Tidak Normal'):
                cell.fill = PatternFill('solid', fgColor='FEE2E2')
                cell.font = Font(bold=True, color='C00000', size=10)
            elif ri % 2 == 0:
                cell.fill = alt_fill
        ws.row_dimensions[wr].height = 18

    resp = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    resp['Content-Disposition'] = f'attachment; filename="Laporan_Inspeksi_{date.today().strftime("%Y%m%d")}.xlsx"'
    wb.save(resp)
    return resp
