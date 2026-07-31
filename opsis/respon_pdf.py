"""
Generator PDF Respons Pembangkit — meniru PDF Excel Respons Kit:
- Halaman POTRAIT.
- Satu chart per KELOMPOK pembangkit (RESPON_GROUPS), judul "Respons Pembangkit
  <Kelompok>", berisi garis MW tiap unit anggota + garis Frekuensi (dual sumbu).
Chart = SVG inline (tanpa matplotlib), dirender WeasyPrint.
"""
import html as _html

# ukuran plot chart kelompok (px) — lebar hampir selebar halaman potrait
W, H = 720, 210
PADL, PADR, PADT, PADB = 46, 46, 10, 34
PW = W - PADL - PADR
PH = H - PADT - PADB

PAL = ['#ea580c', '#16a34a', '#db2777', '#7c3aed', '#0891b2',
       '#ca8a04', '#be123c', '#4f46e5', '#059669', '#9333ea']


def _x(i, n):
    return PADL if n <= 1 else PADL + PW * i / (n - 1)


def _y(v, lo, hi):
    if hi <= lo:
        return PADT + PH / 2
    return PADT + PH * (1 - (v - lo) / (hi - lo))


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


def _group_svg(freq, lines, hz_lo, hz_hi):
    """Plot: frekuensi (biru, kiri) + MW tiap unit (warna, kanan)."""
    ref = [t for t, _ in freq]
    n = len(ref)
    mw_all = [v for _, s in lines for v in _align(s, ref) if v is not None]
    mw_hi = (max(mw_all) * 1.15) if mw_all else 1
    mw_hi = mw_hi if mw_hi > 0 else 1

    s = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
         f'viewBox="0 0 {W} {H}" font-family="Arial,sans-serif">']
    s.append(f'<rect x="0" y="0" width="{W}" height="{H}" fill="#fff" stroke="#e2e8f0"/>')

    # grid + skala Hz (kiri)
    for k in range(6):
        hz = hz_lo + (hz_hi - hz_lo) * k / 5
        yy = _y(hz, hz_lo, hz_hi)
        s.append(f'<line x1="{PADL}" y1="{yy:.1f}" x2="{PADL+PW}" y2="{yy:.1f}" stroke="#eef2f7"/>')
        s.append(f'<text x="{PADL-5}" y="{yy+3:.1f}" font-size="8" fill="#2563eb" text-anchor="end">{hz:.2f}</text>')
    # skala MW (kanan)
    for k in range(6):
        mw = mw_hi * k / 5
        yy = _y(mw, 0, mw_hi)
        s.append(f'<text x="{PADL+PW+5}" y="{yy+3:.1f}" font-size="8" fill="#ea580c">{mw:.0f}</text>')
    # nominal 50 Hz
    y50 = _y(50.0, hz_lo, hz_hi)
    s.append(f'<line x1="{PADL}" y1="{y50:.1f}" x2="{PADL+PW}" y2="{y50:.1f}" '
             f'stroke="#94a3b8" stroke-width="1" stroke-dasharray="4 3"/>')
    # label waktu (x) ~8 titik
    if n:
        step = max(1, n // 8)
        for i in range(0, n, step):
            xx = _x(i, n)
            lbl = ref[i].strftime('%H:%M:%S')
            s.append(f'<text x="{xx:.1f}" y="{H-8}" font-size="7" fill="#64748b" '
                     f'text-anchor="middle">{lbl}</text>')

    # garis MW tiap unit
    for idx, (nama, seri) in enumerate(lines):
        col = PAL[idx % len(PAL)]
        pts = [(_x(i, n), _y(v, 0, mw_hi)) for i, v in enumerate(_align(seri, ref)) if v is not None]
        if pts:
            s.append(f'<polyline fill="none" stroke="{col}" stroke-width="1.6" points="{_poly(pts)}"/>')
    # garis frekuensi (biru tebal)
    fpts = [(_x(i, n), _y(h, hz_lo, hz_hi)) for i, (_, h) in enumerate(freq)]
    s.append(f'<polyline fill="none" stroke="#1e3a8a" stroke-width="2.2" points="{_poly(fpts)}"/>')
    s.append('</svg>')
    return ''.join(s)


def render_html(a, judul='Respons Pembangkit Sistem Sulbagsel'):
    from opsis.respon_registry import RESPON_GROUPS
    kat = a['kategori'] or '—'
    warna = a['warna']
    df = f"{a['df']:.3f}" if a['df'] is not None else '—'
    tp = a['t_pusat']
    freq = a['freq']
    by_name = {p['nama']: p for p in a['pembangkit']}

    if not freq:
        body = ('<div style="padding:24px;color:#991b1b">Tidak ada data frekuensi '
                'pada jendela event ini.</div>')
    else:
        hz_vals = [h for _, h in freq]
        hz_lo = min(min(hz_vals), 49.6) - 0.05
        hz_hi = max(max(hz_vals), 50.4) + 0.05
        blocks = []
        for grup, anggota in RESPON_GROUPS:
            lines = [(nm, by_name[nm]['series']) for nm in anggota
                     if nm in by_name and by_name[nm].get('series')]
            if not lines:
                continue
            leg = []
            for idx, (nm, _) in enumerate(lines):
                leg.append(f'<span style="color:{PAL[idx % len(PAL)]};">&#9632; {_html.escape(nm)}</span>')
            leg.append('<span style="color:#1e3a8a;">&#9632; Frekuensi</span>')
            blocks.append(
                '<div class="grp">'
                f'<div class="gt">Respons Pembangkit {_html.escape(grup)}</div>'
                f'<div class="lg">{" &nbsp; ".join(leg)}</div>'
                + _group_svg(freq, lines, hz_lo, hz_hi) +
                '</div>')
        body = ''.join(blocks) or '<div style="padding:24px;color:#64748b">Tidak ada data MW pembangkit.</div>'

    return f"""<!DOCTYPE html><html><head><meta charset="utf-8"><style>
@page {{ size: A4 portrait; margin: 10mm; }}
body {{ font-family: Arial, Helvetica, sans-serif; color:#1e293b; font-size:11px; }}
.kop {{ display:flex; align-items:center; justify-content:space-between; border-bottom:2px solid {warna}; padding-bottom:6px; }}
.kop b {{ font-size:13px; }} .kop .l div {{ font-size:10px; color:#64748b; }}
h1 {{ font-size:15px; margin:8px 0 2px; }}
.badge {{ display:inline-block; padding:4px 14px; border-radius:16px; color:#fff; font-weight:800; font-size:13px; background:{warna}; }}
.meta {{ font-size:11px; color:#475569; margin:2px 0 10px; }}
.meta b {{ color:#1e293b; }}
.grp {{ break-inside: avoid; margin-bottom:12px; }}
.gt {{ font-size:12px; font-weight:bold; color:#0f2b5b; }}
.lg {{ font-size:9px; font-weight:bold; margin:1px 0 2px; }}
.grp svg {{ width:100%; height:auto; }}
</style></head><body>
<div class="kop">
  <div class="l"><b>PT PLN (Persero)</b><div>UP2B Sistem Makassar</div></div>
  <div style="text-align:right"><span class="badge">{_html.escape(kat)}</span>
    <div style="font-size:9px;color:#64748b;margin-top:2px;">{tp:%d %b %Y %H:%M:%S}</div></div>
</div>
<h1>{_html.escape(judul)}</h1>
<div class="meta">
  &Delta;f: <b style="color:{warna}">{df} Hz</b> &nbsp;|&nbsp;
  f-min <b>{a['fmin'] if a['fmin'] is not None else '—'}</b> / f-max <b>{a['fmax'] if a['fmax'] is not None else '—'}</b> Hz
  &nbsp;|&nbsp; Arah: <b>{a['arah'] or '—'}</b> &nbsp;|&nbsp;
  Kategori: &Delta;f &lt; 0,2 Aman · 0,2&ndash;0,3 Siaga · &gt; 0,3 Bahaya
</div>
{body}
</body></html>"""


def build_pdf(a, judul='Respons Pembangkit Sistem Sulbagsel'):
    """Render analisis event -> bytes PDF (WeasyPrint)."""
    import weasyprint
    return weasyprint.HTML(string=render_html(a, judul)).write_pdf()
