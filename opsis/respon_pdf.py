"""
Generator PDF Respons Pembangkit — meniru halaman "Grafik" pada Excel Respons Kit
(kop PLN, judul, nilai deviasi frekuensi, kategori, grafik trace, tabel skor).

Grafik dibuat sebagai SVG inline (tanpa matplotlib) lalu dirender ke PDF oleh
WeasyPrint (dependensi yang sudah dipakai modul maintenance).
"""
import datetime
import html as _html

W, H = 980, 380          # kanvas grafik (px)
PADL, PADR, PADT, PADB = 56, 56, 24, 40
PLOT_W = W - PADL - PADR
PLOT_H = H - PADT - PADB

# palet garis MW (untuk pembangkit dengan respons menonjol)
LINE_COLORS = ['#2563eb', '#16a34a', '#db2777', '#7c3aed', '#ea580c',
               '#0891b2', '#ca8a04', '#4f46e5', '#be123c', '#059669']


def _x(i, n):
    if n <= 1:
        return PADL
    return PADL + PLOT_W * i / (n - 1)


def _y(v, lo, hi):
    if hi <= lo:
        return PADT + PLOT_H / 2
    return PADT + PLOT_H * (1 - (v - lo) / (hi - lo))


def _poly(points):
    return ' '.join(f'{px:.1f},{py:.1f}' for px, py in points)


def build_svg(a):
    """Bangun SVG grafik: frekuensi (sumbu kiri) + MW pembangkit (sumbu kanan)."""
    freq = a['freq']
    if not freq:
        return '<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="60">' \
               '<text x="10" y="35" font-size="14" fill="#991b1b">Tidak ada data ' \
               'frekuensi pada jendela ini.</text></svg>' % W

    n = len(freq)
    hz_vals = [h for _, h in freq]
    hz_lo = min(min(hz_vals), 49.5) - 0.05
    hz_hi = max(max(hz_vals), 50.5) + 0.05

    # skala MW dari semua pembangkit yang ditampilkan
    tampil = [p for p in a['pembangkit'] if p.get('series')][:len(LINE_COLORS)]
    mw_all = [v for p in tampil for (_, v) in p['series'] if v is not None]
    mw_hi = (max(mw_all) * 1.1) if mw_all else 1
    mw_lo = 0

    svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
           f'viewBox="0 0 {W} {H}" font-family="Arial,Helvetica,sans-serif">']
    svg.append(f'<rect x="0" y="0" width="{W}" height="{H}" fill="#ffffff"/>')

    # garis grid + label Hz (kiri)
    for k in range(6):
        hz = hz_lo + (hz_hi - hz_lo) * k / 5
        yy = _y(hz, hz_lo, hz_hi)
        svg.append(f'<line x1="{PADL}" y1="{yy:.1f}" x2="{PADL+PLOT_W}" y2="{yy:.1f}" '
                   f'stroke="#eef2f7" stroke-width="1"/>')
        svg.append(f'<text x="{PADL-8}" y="{yy+4:.1f}" font-size="11" fill="#2563eb" '
                   f'text-anchor="end">{hz:.2f}</text>')
    # label MW (kanan)
    for k in range(6):
        mw = mw_lo + (mw_hi - mw_lo) * k / 5
        yy = _y(mw, mw_lo, mw_hi)
        svg.append(f'<text x="{PADL+PLOT_W+8}" y="{yy+4:.1f}" font-size="11" '
                   f'fill="#64748b" text-anchor="start">{mw:.0f}</text>')

    # garis nominal 50 Hz
    y50 = _y(50.0, hz_lo, hz_hi)
    svg.append(f'<line x1="{PADL}" y1="{y50:.1f}" x2="{PADL+PLOT_W}" y2="{y50:.1f}" '
               f'stroke="#94a3b8" stroke-width="1" stroke-dasharray="4 3"/>')

    # garis MW tiap pembangkit (tipis, warna)
    for idx, p in enumerate(tampil):
        col = LINE_COLORS[idx % len(LINE_COLORS)]
        pts = [(_x(i, n), _y(v, mw_lo, mw_hi))
               for i, (_, v) in enumerate(_align(p['series'], freq))]
        svg.append(f'<polyline fill="none" stroke="{col}" stroke-width="1.4" '
                   f'opacity="0.85" points="{_poly(pts)}"/>')

    # garis frekuensi (tebal, biru)
    fpts = [(_x(i, n), _y(h, hz_lo, hz_hi)) for i, (_, h) in enumerate(freq)]
    svg.append(f'<polyline fill="none" stroke="#1e3a8a" stroke-width="2.4" '
               f'points="{_poly(fpts)}"/>')

    # penanda ekstrem (nadir/puncak) sesuai kategori
    if a.get('df') is not None:
        target = a['fmin'] if a['arah'] == 'turun' else a['fmax']
        for i, (_, h) in enumerate(freq):
            if abs(h - target) < 1e-6:
                cx, cy = _x(i, n), _y(h, hz_lo, hz_hi)
                svg.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="4.5" '
                           f'fill="{a["warna"]}"/>')
                break

    # judul sumbu
    svg.append(f'<text x="{PADL}" y="{H-8}" font-size="11" fill="#2563eb">■ Frekuensi (Hz)</text>')
    svg.append(f'<text x="{PADL+140}" y="{H-8}" font-size="11" fill="#64748b">■ MW pembangkit (sumbu kanan)</text>')
    svg.append('</svg>')
    return ''.join(svg)


def _align(series, freq):
    """Selaraskan panjang seri MW dengan jumlah titik frekuensi (nearest)."""
    if not series:
        return [(t, None) for t, _ in freq]
    out = []
    for t, _ in freq:
        best = min(series, key=lambda s: abs((s[0] - t).total_seconds()))
        out.append((t, best[1]))
    return out


def render_html(a, judul='Respons Pembangkit Sistem Sulbagsel'):
    """HTML satu halaman siap dirender WeasyPrint."""
    svg = build_svg(a)
    kat = a['kategori'] or '—'
    warna = a['warna']
    df = f"{a['df']:.3f}" if a['df'] is not None else '—'
    tp = a['t_pusat']
    baris = []
    for p in a['pembangkit']:
        d = p['delta_mw']
        d_str = ('+' if (d or 0) > 0 else '') + (f'{d:.2f}' if d is not None else '—')
        if p['arah_benar'] is True:
            stat, sc = 'Merespons', '#16a34a'
        elif p['arah_benar'] is False:
            stat, sc = 'Tidak sesuai', '#dc2626'
        else:
            stat, sc = '—', '#94a3b8'
        baris.append(
            f"<tr><td>{_html.escape(p['nama'])}</td>"
            f"<td class='n'>{p['baseline'] if p['baseline'] is not None else '—'}</td>"
            f"<td class='n'>{p['saat_event'] if p['saat_event'] is not None else '—'}</td>"
            f"<td class='n' style='color:{sc};font-weight:700'>{d_str}</td>"
            f"<td style='color:{sc};font-weight:600'>{stat}</td></tr>")
    tabel = ''.join(baris) or "<tr><td colspan='5' style='text-align:center;color:#94a3b8'>Tidak ada data MW pembangkit.</td></tr>"

    return f"""<!DOCTYPE html><html><head><meta charset="utf-8"><style>
@page {{ size: A4 landscape; margin: 12mm; }}
body {{ font-family: Arial, Helvetica, sans-serif; color:#1e293b; font-size:11px; }}
.kop {{ display:flex; align-items:center; justify-content:space-between; border-bottom:2px solid {warna}; padding-bottom:6px; }}
.kop .l b {{ font-size:13px; }} .kop .l div {{ font-size:10px; color:#64748b; }}
h1 {{ font-size:16px; margin:10px 0 2px; }}
.badge {{ display:inline-block; padding:4px 14px; border-radius:16px; color:#fff; font-weight:800; font-size:13px; background:{warna}; }}
.meta {{ font-size:11px; color:#475569; margin:2px 0 8px; }}
.meta b {{ color:#1e293b; }}
table {{ width:100%; border-collapse:collapse; margin-top:8px; font-size:10.5px; }}
th {{ background:#0f2b5b; color:#fff; padding:4px 6px; text-align:left; }}
td {{ border-bottom:1px solid #e2e8f0; padding:3px 6px; }}
td.n {{ text-align:right; font-variant-numeric:tabular-nums; }}
svg {{ width:100%; height:auto; border:1px solid #e2e8f0; border-radius:6px; }}
</style></head><body>
<div class="kop">
  <div class="l"><b>PT PLN (Persero)</b><div>UP2B Sistem Makassar</div></div>
  <div style="text-align:right"><span class="badge">{_html.escape(kat)}</span></div>
</div>
<h1>{_html.escape(judul)}</h1>
<div class="meta">
  Waktu event: <b>{tp:%d-%m-%Y %H:%M:%S}</b> &nbsp;|&nbsp;
  Deviasi frekuensi (&Delta;f): <b style="color:{warna}">{df} Hz</b> &nbsp;|&nbsp;
  f-min: <b>{a['fmin'] if a['fmin'] is not None else '—'}</b> Hz &nbsp;
  f-max: <b>{a['fmax'] if a['fmax'] is not None else '—'}</b> Hz &nbsp;|&nbsp;
  Arah: <b>{a['arah'] or '—'}</b>
</div>
{svg}
<table>
  <thead><tr><th>Pembangkit</th><th style="text-align:right">Baseline (MW)</th>
  <th style="text-align:right">Saat Event (MW)</th><th style="text-align:right">&Delta;MW</th>
  <th>Respons</th></tr></thead>
  <tbody>{tabel}</tbody>
</table>
<div style="margin-top:8px;font-size:9px;color:#94a3b8">
  Kategori: &Delta;f &lt; 0,2 Hz = Aman &nbsp;|&nbsp; 0,2–0,3 Hz = Siaga &nbsp;|&nbsp; &gt; 0,3 Hz = Bahaya.
  Dibuat otomatis oleh FASOP dari historian SCADA.
</div>
</body></html>"""


def build_pdf(a, judul='Respons Pembangkit Sistem Sulbagsel'):
    """Render analisis event -> bytes PDF (WeasyPrint)."""
    import weasyprint
    return weasyprint.HTML(string=render_html(a, judul)).write_pdf()
