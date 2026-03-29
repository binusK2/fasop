from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Sum
from django.http import JsonResponse
from datetime import date

from .models import AlatUji, Sparepart, MutasiSparepart


# ── Decorator helpers ────────────────────────────────────────────────────────

def can_manage(user):
    """Admin & asisten manager boleh kelola master data."""
    return user.is_superuser or (
        hasattr(user, 'profile') and user.profile.is_asisten_manager
    )


# ════════════════════════════════════════════════════════════════════════════
# ALAT UJI
# ════════════════════════════════════════════════════════════════════════════

@login_required
def alat_list(request):
    qs = AlatUji.objects.filter(is_deleted=False)

    q = request.GET.get('q', '').strip()
    if q:
        qs = qs.filter(
            Q(nama__icontains=q) |
            Q(kategori__icontains=q) |
            Q(merk__icontains=q) |
            Q(nomor_seri__icontains=q)
        )

    kondisi = request.GET.get('kondisi', '').strip()
    if kondisi:
        qs = qs.filter(kondisi=kondisi)

    # Hitung summary
    total       = AlatUji.objects.filter(is_deleted=False).count()
    baik        = AlatUji.objects.filter(is_deleted=False, kondisi='baik').count()
    kalibrasi   = AlatUji.objects.filter(is_deleted=False, kondisi='kalibrasi').count()
    rusak       = AlatUji.objects.filter(is_deleted=False, kondisi__in=['rusak', 'perbaikan']).count()
    overdue     = [a for a in AlatUji.objects.filter(
        is_deleted=False,
        jadwal_kalibrasi_berikut__isnull=False,
        jadwal_kalibrasi_berikut__lt=date.today()
    )]

    return render(request, 'gudang/alat_list.html', {
        'alat_list':        qs,
        'q':                q,
        'kondisi_filter':   kondisi,
        'kondisi_choices':  AlatUji.KONDISI_CHOICES,
        'total':            total,
        'baik':             baik,
        'kalibrasi':        kalibrasi,
        'rusak':            rusak,
        'overdue_count':    len(overdue),
        'can_manage':       can_manage(request.user),
    })


@login_required
def alat_detail(request, pk):
    alat = get_object_or_404(AlatUji, pk=pk, is_deleted=False)
    return render(request, 'gudang/alat_detail.html', {
        'alat':       alat,
        'can_manage': can_manage(request.user),
    })


@login_required
def alat_create(request):
    if not can_manage(request.user):
        messages.error(request, 'Anda tidak memiliki akses untuk menambah alat.')
        return redirect('gudang:alat_list')

    if request.method == 'POST':
        try:
            alat = AlatUji(
                nama                     = request.POST.get('nama', '').strip(),
                kategori                 = request.POST.get('kategori', '').strip(),
                merk                     = request.POST.get('merk', '').strip(),
                model                    = request.POST.get('model', '').strip(),
                nomor_seri               = request.POST.get('nomor_seri', '').strip(),
                kondisi                  = request.POST.get('kondisi', 'baik'),
                lokasi_penyimpanan       = request.POST.get('lokasi_penyimpanan', '').strip(),
                tanggal_kalibrasi        = request.POST.get('tanggal_kalibrasi') or None,
                jadwal_kalibrasi_berikut = request.POST.get('jadwal_kalibrasi_berikut') or None,
                keterangan               = request.POST.get('keterangan', '').strip(),
                created_by               = request.user,
            )
            if request.FILES.get('foto'):
                alat.foto = request.FILES['foto']
            alat.save()
            messages.success(request, f'Alat "{alat.nama}" berhasil ditambahkan.')
            return redirect('gudang:alat_detail', pk=alat.pk)
        except Exception as e:
            messages.error(request, f'Gagal menyimpan: {e}')

    return render(request, 'gudang/alat_form.html', {
        'kondisi_choices': AlatUji.KONDISI_CHOICES,
        'mode': 'create',
    })


@login_required
def alat_edit(request, pk):
    if not can_manage(request.user):
        messages.error(request, 'Anda tidak memiliki akses.')
        return redirect('gudang:alat_list')

    alat = get_object_or_404(AlatUji, pk=pk, is_deleted=False)

    if request.method == 'POST':
        try:
            alat.nama                     = request.POST.get('nama', '').strip()
            alat.kategori                 = request.POST.get('kategori', '').strip()
            alat.merk                     = request.POST.get('merk', '').strip()
            alat.model                    = request.POST.get('model', '').strip()
            alat.nomor_seri               = request.POST.get('nomor_seri', '').strip()
            alat.kondisi                  = request.POST.get('kondisi', 'baik')
            alat.lokasi_penyimpanan       = request.POST.get('lokasi_penyimpanan', '').strip()
            alat.tanggal_kalibrasi        = request.POST.get('tanggal_kalibrasi') or None
            alat.jadwal_kalibrasi_berikut = request.POST.get('jadwal_kalibrasi_berikut') or None
            alat.keterangan               = request.POST.get('keterangan', '').strip()
            if request.FILES.get('foto'):
                alat.foto = request.FILES['foto']
            alat.save()
            messages.success(request, f'Alat "{alat.nama}" berhasil diperbarui.')
            return redirect('gudang:alat_detail', pk=alat.pk)
        except Exception as e:
            messages.error(request, f'Gagal menyimpan: {e}')

    return render(request, 'gudang/alat_form.html', {
        'alat':            alat,
        'kondisi_choices': AlatUji.KONDISI_CHOICES,
        'mode':            'edit',
    })


@login_required
def alat_delete(request, pk):
    if not can_manage(request.user):
        return JsonResponse({'error': 'Akses ditolak.'}, status=403)
    alat = get_object_or_404(AlatUji, pk=pk, is_deleted=False)
    alat.is_deleted = True
    alat.save()
    messages.success(request, f'Alat "{alat.nama}" dihapus.')
    return redirect('gudang:alat_list')


# ════════════════════════════════════════════════════════════════════════════
# SPARE PART
# ════════════════════════════════════════════════════════════════════════════

@login_required
def sparepart_list(request):
    qs = Sparepart.objects.filter(is_deleted=False)

    q = request.GET.get('q', '').strip()
    if q:
        qs = qs.filter(
            Q(nama__icontains=q) |
            Q(kategori__icontains=q) |
            Q(merk__icontains=q) |
            Q(part_number__icontains=q)
        )

    filter_stok = request.GET.get('stok', '').strip()

    # Attach stok ke tiap item (untuk sorting/filter di template)
    items = []
    for sp in qs:
        stok = sp.stok_sekarang
        items.append({'obj': sp, 'stok': stok, 'kritis': stok <= sp.stok_minimum})

    if filter_stok == 'kritis':
        items = [i for i in items if i['kritis']]
    elif filter_stok == 'habis':
        items = [i for i in items if i['stok'] <= 0]

    total       = Sparepart.objects.filter(is_deleted=False).count()
    kritis_count = sum(1 for i in items if i['kritis'])

    return render(request, 'gudang/sparepart_list.html', {
        'items':        items,
        'q':            q,
        'filter_stok':  filter_stok,
        'total':        total,
        'kritis_count': kritis_count,
        'can_manage':   can_manage(request.user),
    })


@login_required
def sparepart_detail(request, pk):
    sp      = get_object_or_404(Sparepart, pk=pk, is_deleted=False)
    mutasi  = MutasiSparepart.objects.filter(sparepart=sp).select_related(
        'dilakukan_oleh', 'terkait_gangguan', 'terkait_maintenance'
    )
    return render(request, 'gudang/sparepart_detail.html', {
        'sp':         sp,
        'mutasi':     mutasi,
        'stok':       sp.stok_sekarang,
        'can_manage': can_manage(request.user),
    })


@login_required
def sparepart_create(request):
    if not can_manage(request.user):
        messages.error(request, 'Anda tidak memiliki akses.')
        return redirect('gudang:sparepart_list')

    if request.method == 'POST':
        try:
            sp = Sparepart(
                nama               = request.POST.get('nama', '').strip(),
                kategori           = request.POST.get('kategori', '').strip(),
                merk               = request.POST.get('merk', '').strip(),
                part_number        = request.POST.get('part_number', '').strip(),
                satuan             = request.POST.get('satuan', 'pcs'),
                lokasi_penyimpanan = request.POST.get('lokasi_penyimpanan', '').strip(),
                stok_minimum       = int(request.POST.get('stok_minimum', 0) or 0),
                keterangan         = request.POST.get('keterangan', '').strip(),
                created_by         = request.user,
            )
            if request.FILES.get('foto'):
                sp.foto = request.FILES['foto']
            sp.save()

            # Stok awal (opsional)
            stok_awal = int(request.POST.get('stok_awal', 0) or 0)
            if stok_awal > 0:
                MutasiSparepart.objects.create(
                    sparepart      = sp,
                    tipe           = 'masuk',
                    jumlah         = stok_awal,
                    keperluan      = 'Stok awal saat pendataan',
                    dilakukan_oleh = request.user,
                )

            messages.success(request, f'Spare part "{sp.nama}" berhasil ditambahkan.')
            return redirect('gudang:sparepart_detail', pk=sp.pk)
        except Exception as e:
            messages.error(request, f'Gagal menyimpan: {e}')

    return render(request, 'gudang/sparepart_form.html', {
        'satuan_choices': Sparepart.SATUAN_CHOICES,
        'mode': 'create',
    })


@login_required
def sparepart_edit(request, pk):
    if not can_manage(request.user):
        messages.error(request, 'Anda tidak memiliki akses.')
        return redirect('gudang:sparepart_list')

    sp = get_object_or_404(Sparepart, pk=pk, is_deleted=False)

    if request.method == 'POST':
        try:
            sp.nama               = request.POST.get('nama', '').strip()
            sp.kategori           = request.POST.get('kategori', '').strip()
            sp.merk               = request.POST.get('merk', '').strip()
            sp.part_number        = request.POST.get('part_number', '').strip()
            sp.satuan             = request.POST.get('satuan', 'pcs')
            sp.lokasi_penyimpanan = request.POST.get('lokasi_penyimpanan', '').strip()
            sp.stok_minimum       = int(request.POST.get('stok_minimum', 0) or 0)
            sp.keterangan         = request.POST.get('keterangan', '').strip()
            if request.FILES.get('foto'):
                sp.foto = request.FILES['foto']
            sp.save()
            messages.success(request, f'Spare part "{sp.nama}" berhasil diperbarui.')
            return redirect('gudang:sparepart_detail', pk=sp.pk)
        except Exception as e:
            messages.error(request, f'Gagal menyimpan: {e}')

    return render(request, 'gudang/sparepart_form.html', {
        'sp':             sp,
        'satuan_choices': Sparepart.SATUAN_CHOICES,
        'mode':           'edit',
    })


@login_required
def sparepart_delete(request, pk):
    if not can_manage(request.user):
        return JsonResponse({'error': 'Akses ditolak.'}, status=403)
    sp = get_object_or_404(Sparepart, pk=pk, is_deleted=False)
    sp.is_deleted = True
    sp.save()
    messages.success(request, f'Spare part "{sp.nama}" dihapus.')
    return redirect('gudang:sparepart_list')


# ════════════════════════════════════════════════════════════════════════════
# MUTASI SPARE PART
# ════════════════════════════════════════════════════════════════════════════

@login_required
def mutasi_create(request, pk):
    """Semua role (termasuk teknisi) boleh catat mutasi."""
    sp = get_object_or_404(Sparepart, pk=pk, is_deleted=False)

    if request.method == 'POST':
        tipe    = request.POST.get('tipe', '')
        jumlah  = int(request.POST.get('jumlah', 0) or 0)
        keperluan = request.POST.get('keperluan', '').strip()

        if tipe not in ('masuk', 'keluar'):
            messages.error(request, 'Tipe mutasi tidak valid.')
            return redirect('gudang:sparepart_detail', pk=pk)

        if jumlah <= 0:
            messages.error(request, 'Jumlah harus lebih dari 0.')
            return redirect('gudang:sparepart_detail', pk=pk)

        if tipe == 'keluar' and jumlah > sp.stok_sekarang:
            messages.error(request, f'Stok tidak cukup. Stok saat ini: {sp.stok_sekarang} {sp.satuan}.')
            return redirect('gudang:sparepart_detail', pk=pk)

        gangguan_id    = request.POST.get('terkait_gangguan') or None
        maintenance_id = request.POST.get('terkait_maintenance') or None

        MutasiSparepart.objects.create(
            sparepart           = sp,
            tipe                = tipe,
            jumlah              = jumlah,
            keperluan           = keperluan,
            terkait_gangguan_id = gangguan_id,
            terkait_maintenance_id = maintenance_id,
            dilakukan_oleh      = request.user,
        )

        label = 'masuk' if tipe == 'masuk' else 'keluar'
        messages.success(request, f'Mutasi {label} {jumlah} {sp.satuan} berhasil dicatat.')
        return redirect('gudang:sparepart_detail', pk=pk)

    # GET — ambil data untuk dropdown gangguan & maintenance
    from gangguan.models import Gangguan
    from maintenance.models import Maintenance
    gangguan_list    = Gangguan.objects.filter(status__in=['open', 'in_progress']).order_by('-tanggal_gangguan')
    maintenance_list = Maintenance.objects.exclude(status='Done').order_by('-date')

    return render(request, 'gudang/mutasi_form.html', {
        'sp':               sp,
        'stok':             sp.stok_sekarang,
        'gangguan_list':    gangguan_list,
        'maintenance_list': maintenance_list,
    })
