"""
Step 1 dari 2 — Generate rencana rename nama perangkat.

Jalankan:
    python manage.py generate_rename_plan
    python manage.py generate_rename_plan --output rename_plan.csv

Output CSV: id, jenis, lokasi, nama_lama, nama_usulan, status
Status: AUTO (aman diapply), REVIEW (perlu cek manual), OK (sudah sesuai)

Setelah review CSV → jalankan apply_rename_plan.
"""
import re
import csv
import sys
from collections import defaultdict
from django.core.management.base import BaseCommand
from devices.models import Device


# ── Helpers ───────────────────────────────────────────────────────────

def _clean(s):
    """Hapus spasi berlebih, strip."""
    return re.sub(r'  +', ' ', s.strip())


def _to_upper_loc(loc):
    """Paksa lokasi ke ALL CAPS."""
    return loc.upper()


def _extract_gi(name):
    """
    Ekstrak nama lokasi dari nama perangkat.
    Cari ' GI ', ' GIS ', ' PB ', ' UP2B', ' PLTMG ' sebagai penanda lokasi.
    Return (prefix_before_gi, gi_keyword, location_after) atau None.
    """
    m = re.search(
        r'\b(GIS?|PB|UP2B|PLTMG|PLTU|PLTP|PLTD|PLTM|PLTA)\s+(.+)',
        name, re.IGNORECASE
    )
    if m:
        return m.group(1).upper(), _clean(m.group(2)).upper()
    return None, None


# ── Rules per jenis ───────────────────────────────────────────────────

def _rename_multiplexer(name, all_names_same_gi):
    """MUX #[N] GI [LOKASI]"""
    up = _clean(name).upper()

    # Ekstrak nomor (berbagai posisi)
    num_match = re.search(r'#?\s*(\d+)\s*#?', up)
    number = int(num_match.group(1)) if num_match else None

    # Ekstrak lokasi
    gi_kw, location = _extract_gi(up)
    if not location:
        # Coba tanpa keyword GI (misal "MUX 1# BUNGKU")
        parts = re.split(r'#?\s*\d+\s*#?', up, maxsplit=1)
        location = _clean(parts[-1]).strip() if len(parts) > 1 else None

    if number is None or not location:
        return None, 'REVIEW'

    gi_kw = gi_kw or 'GI'
    proposed = f'MUX #{number} {gi_kw} {location}'
    status = 'AUTO' if proposed.upper() != up.upper() else 'OK'
    return proposed, status


def _rename_radio(name):
    """RADIO [GI/PB/..] [LOKASI] — hanya fix spasi ganda & casing lokasi."""
    cleaned = _clean(name)
    # Jika sudah normal, cek apakah ada double space yang perlu fix
    fixed = re.sub(r'  +', ' ', cleaned).strip()
    # Casing: RADIO harus kapital, sisanya ALL CAPS
    parts = fixed.split(' ', 1)
    if len(parts) == 2:
        proposed = 'RADIO ' + parts[1].upper()
    else:
        proposed = 'RADIO'
    status = 'AUTO' if proposed != name else 'OK'
    return proposed, status


def _rename_master_clock(name):
    """MC GI [LOKASI]"""
    cleaned = _clean(name).upper()
    # Ganti MASTER CLOCK → MC
    fixed = re.sub(r'\bMASTER\s+CLOCK\b', 'MC', cleaned)
    # Fix spasi
    fixed = re.sub(r'  +', ' ', fixed).strip()
    status = 'AUTO' if fixed != name.upper() else 'OK'
    return fixed, status


def _rename_rectifier(name):
    """RECTIFIER [MERK] GI [LOKASI] — fix spasi & typo CLORIDE."""
    cleaned = _clean(name).upper()
    # Fix known typos
    fixed = re.sub(r'\bCLORIDE\b', 'CHLORIDE', cleaned)
    fixed = re.sub(r'  +', ' ', fixed).strip()
    status = 'AUTO' if fixed != name.upper() else 'OK'
    return fixed, status


def _rename_dfr(name, count_at_gi):
    """DFR #[N] GI [LOKASI] — selalu pakai nomor."""
    up = _clean(name).upper()

    # Sudah punya nomor
    num_match = re.search(r'#(\d+)', up)
    if num_match:
        # Cek notasi aneh: #2_1 → tandai REVIEW
        if re.search(r'#\d+_\d+', up):
            return None, 'REVIEW'
        # Sudah format benar, hanya fix spasi/typo
        fixed = re.sub(r'  +', ' ', up).strip()
        status = 'AUTO' if fixed != up else 'OK'
        return fixed, status

    # Tidak punya nomor → tambahkan #1
    # Tapi kalau di GI yang sama sudah ada yang bernomor → REVIEW
    if count_at_gi > 1:
        return None, 'REVIEW'

    gi_kw, location = _extract_gi(up)
    if not location:
        return None, 'REVIEW'

    gi_kw = gi_kw or 'GI'
    proposed = f'DFR #1 {gi_kw} {location}'
    return proposed, 'AUTO'


def _rename_switch_sas(name):
    """
    Standarisasi separator bay → hash (#).
    SWITCH BAY TRAFO-1  → SWITCH BAY TRAFO#1
    SWITCH BAY COMMON 150 → SWITCH BAY COMMON#150
    """
    up = _clean(name).upper()

    # Fix double space
    fixed = re.sub(r'  +', ' ', up).strip()

    # Ganti hyphen+angka menjadi hash: TRAFO-1 → TRAFO#1
    fixed = re.sub(r'([A-Z])-(\d+)', r'\1#\2', fixed)

    # COMMON 150 / IBT 1 150 → COMMON#150 / IBT#1 150
    # Hanya kalau kata sebelumnya adalah COMMON atau IBT atau FEEDER
    fixed = re.sub(r'\b(COMMON|FEEDER|IBT)\s+(\d+)', r'\1#\2', fixed)

    # KONTROL → fix (bukan CONTROL)
    fixed = re.sub(r'\bCONTROL\b', 'KONTROL', fixed)

    # ETH SWITCH SAS → beda format, flag REVIEW
    if fixed.startswith('ETH '):
        return None, 'REVIEW'

    status = 'AUTO' if fixed != up else 'OK'
    return fixed, status


def _rename_switch_general(name):
    """SwOS CRS GI [LOKASI] — standarkan casing lokasi ke ALL CAPS."""
    cleaned = _clean(name)
    # SwOS CRS prefix harus persis (mixed case by design)
    if not re.match(r'^SwOS\s+CRS\s+', cleaned, re.IGNORECASE):
        return None, 'REVIEW'

    m = re.match(r'^(SwOS\s+CRS\s+)(.*)', cleaned, re.IGNORECASE)
    if not m:
        return None, 'REVIEW'

    prefix   = 'SwOS CRS '
    location = _clean(m.group(2)).upper()
    # DayaBaru → DAYA BARU (insert space before capital letters)
    location = re.sub(r'([a-z])([A-Z])', r'\1 \2', location).upper()

    proposed = prefix + location
    status = 'AUTO' if proposed != cleaned else 'OK'
    return proposed, status


def _rename_voip(name):
    """VoIP [PREFIX] [LOKASI] — standarkan casing lokasi ke ALL CAPS setelah VoIP."""
    cleaned = _clean(name)
    if not cleaned.upper().startswith('VOIP'):
        return None, 'REVIEW'
    # Pertahankan VoIP (mixed case)
    rest = cleaned[4:].strip()  # hapus "VoIP"/"VOIP"/dll
    rest = rest.upper()
    proposed = 'VoIP ' + rest
    # Fix double space
    proposed = re.sub(r'  +', ' ', proposed).strip()
    status = 'AUTO' if proposed != cleaned else 'OK'
    return proposed, status


def _rename_ied_bcu(name):
    """BCU BAY [IDENTIFIER] GI [LOKASI] — fix spasi & standarisasi hash."""
    up = _clean(name).upper()
    fixed = re.sub(r'  +', ' ', up).strip()
    # Fix spacing di hash: "IBT #1" → "IBT#1"
    fixed = re.sub(r'([A-Z0-9])\s+#(\d+)', r'\1#\2', fixed)
    status = 'AUTO' if fixed != up else 'OK'
    return fixed, status


def _rename_plc(name):
    """
    PLC [MERK] [TITIK A] - [TITIK B]
    Hanya fix spacing/casing. Tidak ubah endpoint karena butuh konteks.
    """
    up = _clean(name).upper()
    # Standarkan " - " (dengan spasi) sebagai separator endpoint
    fixed = re.sub(r'\s*-\s*', ' - ', up)
    fixed = re.sub(r'  +', ' ', fixed).strip()
    # Jika masih pakai format ARAH → flag REVIEW
    if re.search(r'\bARAH\b', fixed):
        return None, 'REVIEW'
    status = 'AUTO' if fixed != up else 'OK'
    return fixed, status


def _rename_ufls(name):
    """UFR [N] GI [LOKASI] — fix anomali tanpa prefix."""
    up = _clean(name).upper()
    if not up.startswith('UFR') and not up.startswith('UFLS'):
        return None, 'REVIEW'
    fixed = re.sub(r'  +', ' ', up).strip()
    status = 'AUTO' if fixed != up else 'OK'
    return fixed, status


# ── Dispatcher ────────────────────────────────────────────────────────

RENAME_RULES = {
    'RADIO':              _rename_radio,
    'MASTER CLOCK':       _rename_master_clock,
    'CATU DAYA':          _rename_rectifier,
    'RECTIFIER':          _rename_rectifier,
    'VOIP':               _rename_voip,
    'IED BCU':            _rename_ied_bcu,
    'SWITCH SAS':         _rename_switch_sas,
    'SWITCH':             _rename_switch_general,
    'UFLS':               _rename_ufls,
    'UFR ISLAND':         _rename_ufls,
    'PLC':                _rename_plc,
}

SPECIAL_RULES = {'MULTIPLEXER', 'DFR'}


class Command(BaseCommand):
    help = 'Generate rencana rename nama perangkat (Step 1). Output CSV untuk direview.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--output', default='-',
            help='Path file CSV output (default: stdout / -)',
        )
        parser.add_argument(
            '--jenis', nargs='*', metavar='JENIS',
            help='Filter jenis tertentu',
        )
        parser.add_argument(
            '--only-changes', action='store_true',
            help='Hanya tampilkan yang akan berubah (skip OK)',
        )

    def handle(self, *args, **options):
        qs = Device.objects.filter(
            is_deleted=False, host__isnull=True
        ).select_related('jenis').order_by('jenis__name', 'nama')

        if options['jenis']:
            qs = qs.filter(jenis__name__in=options['jenis'])

        devices = list(qs)

        # ── Pra-hitung: jumlah DFR & MUX per GI ──────────────────
        dfr_per_gi   = defaultdict(list)
        mux_per_gi   = defaultdict(list)
        for dev in devices:
            jenis = (dev.jenis.name if dev.jenis else '').upper()
            if jenis == 'DFR':
                gi_kw, loc = _extract_gi(dev.nama.upper())
                if loc:
                    dfr_per_gi[loc].append(dev.nama)
            elif jenis == 'MULTIPLEXER':
                gi_kw, loc = _extract_gi(dev.nama.upper())
                if loc:
                    mux_per_gi[loc].append(dev.nama)

        # ── Build rows ────────────────────────────────────────────
        rows = []
        for dev in devices:
            jenis = (dev.jenis.name if dev.jenis else '(Tanpa Jenis)').upper()
            nama  = dev.nama

            proposed, status = None, 'SKIP'

            if jenis in RENAME_RULES:
                fn = RENAME_RULES[jenis]
                proposed, status = fn(nama)

            elif jenis == 'MULTIPLEXER':
                gi_kw, loc = _extract_gi(nama.upper())
                loc_key = loc or ''
                proposed, status = _rename_multiplexer(nama, mux_per_gi.get(loc_key, []))

            elif jenis == 'DFR':
                gi_kw, loc = _extract_gi(nama.upper())
                loc_key = loc or ''
                count = len(dfr_per_gi.get(loc_key, []))
                proposed, status = _rename_dfr(nama, count)

            else:
                # Jenis lain: hanya fix spasi ganda
                fixed = re.sub(r'  +', ' ', nama).strip()
                if fixed != nama:
                    proposed, status = fixed, 'AUTO'
                else:
                    proposed, status = nama, 'OK'

            if proposed is None:
                proposed = nama  # REVIEW: tampilkan nama lama sebagai placeholder

            rows.append({
                'id':          dev.pk,
                'jenis':       dev.jenis.name if dev.jenis else '',
                'lokasi':      dev.lokasi or '',
                'nama_lama':   nama,
                'nama_usulan': proposed,
                'status':      status,
            })

        # ── Filter ────────────────────────────────────────────────
        if options['only_changes']:
            rows = [r for r in rows if r['status'] != 'OK' and r['status'] != 'SKIP']

        # ── Output ────────────────────────────────────────────────
        out = open(options['output'], 'w', newline='', encoding='utf-8') \
              if options['output'] != '-' else sys.stdout

        writer = csv.DictWriter(out, fieldnames=[
            'id', 'jenis', 'lokasi', 'nama_lama', 'nama_usulan', 'status'
        ])
        writer.writeheader()
        writer.writerows(rows)

        if options['output'] != '-':
            out.close()

        # ── Summary ke stderr ─────────────────────────────────────
        auto   = sum(1 for r in rows if r['status'] == 'AUTO')
        review = sum(1 for r in rows if r['status'] == 'REVIEW')
        ok     = sum(1 for r in rows if r['status'] == 'OK')
        skip   = sum(1 for r in rows if r['status'] == 'SKIP')

        self.stderr.write(f'\n  Total    : {len(rows)} perangkat')
        self.stderr.write(f'  AUTO     : {auto}  (aman diapply otomatis)')
        self.stderr.write(f'  REVIEW   : {review}  (perlu cek manual di CSV)')
        self.stderr.write(f'  OK       : {ok}  (sudah sesuai, tidak berubah)')
        self.stderr.write(f'  SKIP     : {skip}  (jenis tidak ditangani)')
        self.stderr.write(f'\n  Edit kolom nama_usulan untuk yang REVIEW,')
        self.stderr.write(f'  lalu jalankan: python manage.py apply_rename_plan rename_plan.csv\n')
