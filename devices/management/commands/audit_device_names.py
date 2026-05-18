"""
Audit nama perangkat — cari pola tidak konsisten per jenis.

Jalankan:
    python manage.py audit_device_names
    python manage.py audit_device_names --jenis DFR MULTIPLEXER
    python manage.py audit_device_names --csv > audit.csv
"""
import re
from collections import defaultdict
from django.core.management.base import BaseCommand
from devices.models import Device


def _normalize(name):
    """Lowercase, collapse whitespace, strip."""
    return re.sub(r'\s+', ' ', name.strip().lower())


def _detect_patterns(names):
    """
    Kembalikan dict berisi pattern yang terdeteksi dari list nama:
      - prefixes  : bagian sebelum ' GI' / ' bay' / angka
      - has_gi    : mengandung ' GI '
      - has_number: mengandung # atau angka ordinal
      - has_brand : mengandung nama merk umum
    """
    BRANDS = {'abb','siemens','ge','areva','schneider','cisco','mikrotik',
              'huawei','hirschmann','moxa','advantech','reyrolle','alstom',
              'beckwith','schweitzer','sel','nari','xuji','comnet','ruggedcom'}

    patterns = []
    for n in names:
        low = _normalize(n)
        p = {
            'has_gi':     bool(re.search(r'\bgi\b', low)),
            'has_number': bool(re.search(r'#\d+|\b\d+\b', low)),
            'has_brand':  any(b in low.split() for b in BRANDS),
            'all_upper':  n == n.upper(),
            'all_lower':  n == n.lower(),
            'mixed_case': (n != n.upper() and n != n.lower()),
            'has_special': bool(re.search(r'[_/\\]', n)),
        }
        patterns.append(p)
    return patterns


def _issues(name, all_names_in_jenis):
    """Return list of issue strings for a single name."""
    issues = []
    low = name.strip().lower()

    # Spasi berlebih
    if re.search(r'  +', name):
        issues.append('spasi ganda')

    # Trailing/leading whitespace
    if name != name.strip():
        issues.append('whitespace di tepi')

    # Campuran huruf besar-kecil tidak beraturan (bukan Title Case atau ALL CAPS)
    words = name.split()
    if len(words) > 1:
        casing = set()
        for w in words:
            if w.isupper():
                casing.add('upper')
            elif w.islower():
                casing.add('lower')
            elif w.istitle():
                casing.add('title')
            else:
                casing.add('mixed')
        if len(casing) > 2:
            issues.append('inkonsistensi huruf besar/kecil')

    # Karakter tidak standar
    if re.search(r'[_\\]', name):
        issues.append('karakter tidak standar (_ atau \\)')

    return issues


class Command(BaseCommand):
    help = 'Audit nama perangkat — laporan pola & inkonsistensi per jenis'

    def add_arguments(self, parser):
        parser.add_argument(
            '--jenis', nargs='*', metavar='JENIS',
            help='Filter jenis tertentu (default: semua)',
        )
        parser.add_argument(
            '--csv', action='store_true',
            help='Output format CSV (untuk import ke spreadsheet)',
        )
        parser.add_argument(
            '--min-count', type=int, default=2,
            help='Hanya tampilkan jenis dengan minimal N perangkat (default: 2)',
        )

    def handle(self, *args, **options):
        qs = Device.objects.filter(is_deleted=False, host__isnull=True).select_related('jenis')

        if options['jenis']:
            qs = qs.filter(jenis__name__in=options['jenis'])

        # Kelompokkan per jenis
        by_jenis = defaultdict(list)
        for dev in qs.order_by('jenis__name', 'nama'):
            jenis_name = dev.jenis.name if dev.jenis else '(Tanpa Jenis)'
            by_jenis[jenis_name].append(dev)

        if options['csv']:
            self._output_csv(by_jenis)
        else:
            self._output_report(by_jenis, options['min_count'])

    # ── CSV output ────────────────────────────────────────────────
    def _output_csv(self, by_jenis):
        self.stdout.write('Jenis,Nama Perangkat,Lokasi,Issues')
        for jenis, devs in sorted(by_jenis.items()):
            names = [d.nama for d in devs]
            for dev in devs:
                issues = _issues(dev.nama, names)
                self.stdout.write(
                    f'"{jenis}","{dev.nama}","{dev.lokasi}","{"; ".join(issues) or "-"}"'
                )

    # ── Human-readable report ─────────────────────────────────────
    def _output_report(self, by_jenis, min_count):
        SEP  = '─' * 72
        SEP2 = '═' * 72

        self.stdout.write(f'\n{SEP2}')
        self.stdout.write('  AUDIT NAMA PERANGKAT')
        self.stdout.write(SEP2)

        total_devices = sum(len(v) for v in by_jenis.values())
        self.stdout.write(f'  Total perangkat aktif : {total_devices}')
        self.stdout.write(f'  Total jenis           : {len(by_jenis)}')
        self.stdout.write(f'{SEP2}\n')

        for jenis in sorted(by_jenis.keys()):
            devs  = by_jenis[jenis]
            names = [d.nama for d in devs]

            if len(devs) < min_count:
                continue

            self.stdout.write(f'\n{"█ " + jenis.upper():─<72}')
            self.stdout.write(f'  Jumlah perangkat: {len(devs)}')

            # ── Analisis pola ──────────────────────────────────
            patterns = _detect_patterns(names)
            pct_gi     = sum(1 for p in patterns if p['has_gi'])     / len(patterns) * 100
            pct_number = sum(1 for p in patterns if p['has_number']) / len(patterns) * 100
            pct_brand  = sum(1 for p in patterns if p['has_brand'])  / len(patterns) * 100
            pct_upper  = sum(1 for p in patterns if p['all_upper'])  / len(patterns) * 100
            pct_special= sum(1 for p in patterns if p['has_special'])/ len(patterns) * 100

            self.stdout.write(f'  Pola yang terdeteksi:')
            if pct_gi > 0:
                self.stdout.write(f'    • Mengandung "GI"     : {pct_gi:.0f}% ({sum(1 for p in patterns if p["has_gi"])} dari {len(patterns)})')
            if pct_number > 0:
                self.stdout.write(f'    • Mengandung angka/#  : {pct_number:.0f}% ({sum(1 for p in patterns if p["has_number"])} dari {len(patterns)})')
            if pct_brand > 0:
                self.stdout.write(f'    • Mengandung nama merk: {pct_brand:.0f}% ({sum(1 for p in patterns if p["has_brand"])} dari {len(patterns)})')
            if pct_upper > 0:
                self.stdout.write(f'    • Semua huruf kapital : {pct_upper:.0f}%')
            if pct_special > 0:
                self.stdout.write(f'    • Ada karakter _ atau \\: {pct_special:.0f}%')

            # ── Daftar nama + issues ───────────────────────────
            self.stdout.write(f'\n  {"NAMA PERANGKAT":<55} {"LOKASI":<20} ISSUES')
            self.stdout.write(f'  {SEP}')
            has_issues = False
            for dev in devs:
                issues = _issues(dev.nama, names)
                flag   = '⚠ ' if issues else '  '
                lokasi = str(dev.lokasi)[:18] if dev.lokasi else '—'
                nama   = dev.nama[:53]
                issue_str = ', '.join(issues) if issues else ''
                self.stdout.write(f'  {flag}{nama:<53} {lokasi:<20} {issue_str}')
                if issues:
                    has_issues = True

            # ── Deteksi inkonsistensi format antar nama ────────
            self.stdout.write('')
            self._check_consistency(jenis, names)

        self.stdout.write(f'\n{SEP2}')
        self.stdout.write('  Selesai. Gunakan --csv untuk export ke spreadsheet.')
        self.stdout.write(f'{SEP2}\n')

    def _check_consistency(self, jenis, names):
        """Deteksi variasi format yang berbeda dalam 1 jenis."""
        warnings = []

        # Cek prefix: apakah jenis perangkat disebut di awal nama dengan berbagai cara
        prefixes = set()
        for n in names:
            first = n.split()[0].upper() if n.split() else ''
            prefixes.add(first)
        if len(prefixes) > 1 and len(prefixes) <= 5:
            warnings.append(f'Prefix berbeda-beda: {sorted(prefixes)}')

        # Cek apakah sebagian ada "GI" dan sebagian tidak
        has_gi  = [n for n in names if re.search(r'\bgi\b', n, re.I)]
        no_gi   = [n for n in names if not re.search(r'\bgi\b', n, re.I)]
        if has_gi and no_gi and len(has_gi) > 1 and len(no_gi) > 1:
            warnings.append(f'Sebagian pakai "GI" ({len(has_gi)}), sebagian tidak ({len(no_gi)})')

        # Cek campuran huruf besar dan bukan
        upper_count = sum(1 for n in names if n == n.upper())
        non_upper   = len(names) - upper_count
        if upper_count > 0 and non_upper > 0:
            warnings.append(f'Campuran ALL CAPS ({upper_count}) dan bukan ({non_upper})')

        # Cek pemakaian # vs angka langsung vs tidak ada nomor
        hash_num  = [n for n in names if '#' in n]
        plain_num = [n for n in names if not '#' in n and re.search(r'\b\d+\b', n)]
        if hash_num and plain_num:
            warnings.append(f'Nomor pakai "#" ({len(hash_num)}) vs angka langsung ({len(plain_num)})')

        if warnings:
            self.stdout.write(f'  ⚠  INKONSISTENSI FORMAT:')
            for w in warnings:
                self.stdout.write(f'     → {w}')
        else:
            self.stdout.write(f'  ✓  Format relatif konsisten')
