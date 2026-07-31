"""
Generator PDF Respons Pembangkit — meniru sheet "Grafik" Excel Respons Kit:
kop PLN + kategori + deviasi, lalu GRID chart kecil PER-UNIT, tiap chart
menampilkan MW unit itu terhadap frekuensi sistem (dual sumbu). Semua
pembangkit ikut (yang ada datanya).

Chart dibuat sebagai SVG inline (tanpa matplotlib) lalu dirender WeasyPrint.
"""
import html as _html

# ukuran satu mini-chart (px)
MW, MH = 250, 130
PADL, PADR, PADT, PADB = 30, 26, 8, 16
PW = MW - PADL - PADR
PH = MH - PADT - PADB


def _x(i, n):
    return PADL if n <= 1 else PADL + PW * i / (n - 1)


def _y(v, lo, hi, h=PH, top=PADT):
    if hi <= lo:
        return top + h / 2
    return top + h * (1 - (v - lo) / (hi - lo))


def _poly(pts):
    return ' '.join(f'{x:.1f},{y:.1f}' for x, y in pts)


def _align(series, ref_times):
    if not series:
        return [None] * len(ref_times)
    out = []
    for t in ref_times:
        best = min(series, key=lambda s: abs((s[0] - t).total_seconds()))
        out.append(best[1])
    return out


def _mini_svg(nama, delta, freq, series, hz_lo, hz_hi):
    """Satu chart kecil: frekuensi (biru, kiri) + MW unit (oranye, kanan)."""
    ref = [t for t, _ in freq]
    n = len(ref)
    mw_vals = [v for v in _align(series, ref) if v is not None]
    mw_hi = (max(mw_vals) * 1.15) if mw_vals else 1
    mw_hi = mw_hi if mw_hi > 0 else 1

    s = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{MW}" height="{MH}" '
         f'viewBox="0 0 {MW} {MH}" font-family="Arial,sans-serif">']
    s.append(f'<rect x="0" y="0" width="{MW}" height="{MH}" fill="#ffffff" '
             f'stroke="#e2e8f0"/>')
    # judul unit + ΔMW
    d = ('+' if (delta or 0) > 0 else '') + (f'{delta:.1f}' if delta is not None else '—')
    dc = '#16a34a' if (delta or 0) > 0 else ('#dc2626' if (delta or 0) < 0 else '#64748b')
    s.append(f'<text x="{PADL}" y="12" font-size="9.5" font-weight="bold" fill="#0f2b5b">'
             f'{_html.escape(nama[:22])}</text>')
    s.append(f'<text x="{MW-PADR}" y="12" font-size="9" font-weight="bold" fill="{dc}" '
             f'text-anchor="end">Δ{d}</text>')
    # garis nominal 50 Hz
    y50 = _y(50.0, hz_lo, hz_hi)
    s.append(f'<line x1="{PADL}" y1="{y50:.1f}" x2="{PADL+PW}" y2="{y50:.1f}" '
             f'stroke="#cbd5e1" stroke-width=".7" stroke-dasharray="3 2"/>')
    # sumbu label ringkas
    s.append(f'<text x="{PADL-3}" y="{PADT+8}" font-size="7" fill="#2563eb" text-anchor="end">{hz_hi:.1f}</text>')
    s.append(f'<text x="{PADL-3}" y="{PADT+PH}" font-size="7" fill="#2563eb" text-anchor="end">{hz_lo:.1f}</text>')
    s.append(f'<text x="{MW-PADR+3}" y="{PADT+8}" font-size="7" fill="#ea580c">{mw_hi:.0f}</text>')
    s.append(f'<text x="{MW-PADR+3}" y="{PADT+PH}" font-size="7" fill="#ea580c">0</text>')
    # garis MW unit (oranye)
    apts = [(_x(i, n), _y(v, 0, mw_hi)) for i, v in enumerate(_align(series, ref)) if v is not None]
    if apts:
        s.append(f'<polyline fill="none" stroke="#ea580c" stroke-width="1.4" points="{_poly(apts)}"/>')
    # garis frekuensi (biru)
    fpts = [(_x(i, n), _y(h, hz_lo, hz_hi)) for i, (_, h) in enumerate(freq)]
    s.append(f'<polyline fill="none" stroke="#1e3a8a" stroke-width="1.6" points="{_poly(fpts)}"/>')
    s.append('</svg>')
    return ''.join(s)


def render_html(a, judul='Respons Pembangkit Sistem Sulbagsel'):
    kat = a['kategori'] or '—'
    warna = a['warna']
    df = f"{a['df']:.3f}" if a['df'] is not None else '—'
    tp = a['t_pusat']
    freq = a['freq']

    if not freq:
        charts = ('<div style="padding:24px;color:#991b1b">Tidak ada data frekuensi '
                  'pada jendela event ini.</div>')
    else:
        hz_vals = [h for _, h in freq]
        hz_lo = min(min(hz_vals), 49.6) - 0.05
        hz_hi = max(max(hz_vals), 50.4) + 0.05
        cells = []
        for p in a['pembangkit']:
            if not p.get('series'):
                continue
            cells.append('<div class="cell">'
                         + _mini_svg(p['nama'], p['delta_mw'], freq, p['series'], hz_lo, hz_hi)
                         + '</div>')
        charts = ('<div class="grid">' + ''.join(cells) + '</div>') if cells else \
                 '<div style="padding:24px;color:#64748b">Tidak ada data MW pembangkit.</div>'

    return f"""<!DOCTYPE html><html><head><meta charset="utf-8"><style>
@page {{ size: A4 landscape; margin: 10mm; }}
body {{ font-family: Arial, Helvetica, sans-serif; color:#1e293b; font-size:11px; }}
.kop {{ display:flex; align-items:center; justify-content:space-between; border-bottom:2px solid {warna}; padding-bottom:6px; }}
.kop b {{ font-size:13px; }} .kop .l div {{ font-size:10px; color:#64748b; }}
h1 {{ font-size:15px; margin:8px 0 2px; }}
.badge {{ display:inline-block; padding:4px 14px; border-radius:16px; color:#fff; font-weight:800; font-size:13px; background:{warna}; }}
.meta {{ font-size:11px; color:#475569; margin:2px 0 8px; }}
.meta b {{ color:#1e293b; }}
.legend {{ font-size:9.5px; color:#475569; margin:2px 0 6px; }}
.legend .b {{ color:#1e3a8a; font-weight:bold; }} .legend .o {{ color:#ea580c; font-weight:bold; }}
.grid {{ display:grid; grid-template-columns: repeat(4, 1fr); gap:6px; }}
.cell svg {{ width:100%; height:auto; }}
</style></head><body>
<div class="kop">
  <div class="l"><b>PT PLN (Persero)</b><div>UP2B Sistem Makassar</div></div>
  <div style="text-align:right"><span class="badge">{_html.escape(kat)}</span></div>
</div>
<h1>{_html.escape(judul)}</h1>
<div class="meta">
  Waktu event: <b>{tp:%d-%m-%Y %H:%M:%S}</b> &nbsp;|&nbsp;
  &Delta;f: <b style="color:{warna}">{df} Hz</b> &nbsp;|&nbsp;
  f-min <b>{a['fmin'] if a['fmin'] is not None else '—'}</b> / f-max <b>{a['fmax'] if a['fmax'] is not None else '—'}</b> Hz
  &nbsp;|&nbsp; Arah: <b>{a['arah'] or '—'}</b>
</div>
<div class="legend"><span class="b">■ Frekuensi (Hz)</span> &nbsp; <span class="o">■ MW unit</span>
 &nbsp;|&nbsp; Kategori: &Delta;f &lt; 0,2 = Aman · 0,2–0,3 = Siaga · &gt; 0,3 = Bahaya.</div>
{charts}
</body></html>"""


def build_pdf(a, judul='Respons Pembangkit Sistem Sulbagsel'):
    """Render analisis event -> bytes PDF (WeasyPrint)."""
    import weasyprint
    return weasyprint.HTML(string=render_html(a, judul)).write_pdf()
