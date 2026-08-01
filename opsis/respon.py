"""
Analisis Respons Pembangkit terhadap frekuensi (Primary Frequency Response).

Meniru aplikasi Excel "Respons Kit" (sumber sama: MSSQL SCADA), tetapi memakai
HISTORIAN (lookback) alih-alih polling live:
  - Frekuensi sistem per detik  -> SYS_FREQ_HIS  (opsis.mssql.get_freq_range)
  - MW per pembangkit per detik  -> HIS_MEAS_KIT (opsis.mssql.get_kit_mw_range)

Klasifikasi event (identik Excel — sel DK4):
    df = deviasi frekuensi TERBESAR dari 50 Hz selama jendela event
    df < 0.2       -> Aman
    0.2 <= df <= 0.3 -> Siaga
    df > 0.3       -> Bahaya

Modul ini murni perhitungan; fungsi pengambilan MSSQL disuntikkan (get_freq /
get_mw) agar mudah diuji tanpa database.
"""
import datetime

NOMINAL_HZ    = 50.0
AMBANG_SIAGA  = 0.2   # df >= 0.2  -> minimal Siaga
AMBANG_BAHAYA = 0.3   # df >  0.3  -> Bahaya

KATEGORI_WARNA = {
    'Aman':   '#10b981',
    'Siaga':  '#f59e0b',
    'Bahaya': '#ef4444',
}


def kategori_dari_deviasi(df):
    """df (Hz) -> 'Aman' | 'Siaga' | 'Bahaya' (persis logika Excel DK4)."""
    if df is None:
        return None
    if df < AMBANG_SIAGA:
        return 'Aman'
    if df > AMBANG_BAHAYA:
        return 'Bahaya'
    return 'Siaga'


def deviasi_maks(hz_values):
    """
    Kembalikan (df, fmax, fmin) untuk deret nilai Hz.
    df = MAX(fmax-50, 50-fmin) — deviasi terbesar dari nominal (Excel DI4).
    """
    vals = [float(h) for h in hz_values if h is not None]
    if not vals:
        return None, None, None
    fmax, fmin = max(vals), min(vals)
    df = max(fmax - NOMINAL_HZ, NOMINAL_HZ - fmin)
    return round(df, 4), round(fmax, 3), round(fmin, 3)


def deteksi_events(freq_seq, ambang=AMBANG_SIAGA, jeda_detik=300):
    """
    Temukan event dari deret frekuensi.

    freq_seq : list [(waktu:datetime, hz:float)] terurut waktu.
    ambang   : deviasi minimal (Hz) agar dianggap event (default 0.2 = Siaga).
    jeda_detik: sampel di atas ambang yang berjarak <= ini digabung 1 event.

    Kembalikan list event: {t_ekstrem, hz_ekstrem, df, arah, kategori,
                            t_mulai, t_selesai}
    arah: 'turun' (under-freq) / 'naik' (over-freq).
    """
    tanda = [(t, h, abs(h - NOMINAL_HZ)) for t, h in freq_seq
             if t is not None and h is not None]
    tanda.sort(key=lambda x: x[0])

    events, grup = [], []
    def tutup(grup):
        if not grup:
            return
        # sampel dengan deviasi terbesar = titik ekstrem event
        t_ek, hz_ek, dev = max(grup, key=lambda x: x[2])
        events.append({
            't_ekstrem':  t_ek,
            'hz_ekstrem': round(hz_ek, 3),
            'df':         round(dev, 4),
            'arah':       'turun' if hz_ek < NOMINAL_HZ else 'naik',
            'kategori':   kategori_dari_deviasi(dev),
            't_mulai':    grup[0][0],
            't_selesai':  grup[-1][0],
        })

    for t, h, dev in tanda:
        if dev < ambang:
            continue
        if grup and (t - grup[-1][0]).total_seconds() > jeda_detik:
            tutup(grup); grup = []
        grup.append((t, h, dev))
    tutup(grup)
    return events


def gabung_plants(unit_mw, plants):
    """
    Gabung MW per-unit (B1·B3) menjadi per-PLANT sesuai registry Excel.

    unit_mw : {"<B1> · <B3>": [(waktu, mw)]}  (dari get_all_kit_unit_mw_range)
    plants  : dict {nama: [(B1, B3), …]}      (RESPON_PLANTS) atau list of pairs.
    Return  : {nama: [(waktu_detik, mw_total), …]} — MW plant = jumlah unitnya
              per detik (seperti Excel yang menjumlah unit satu plant).
    """
    items = plants.items() if hasattr(plants, 'items') else plants
    out = {}
    for nama, units in items:
        per_detik = {}
        for b1, b3 in units:
            for t, v in unit_mw.get(f'{b1} · {b3}', []):
                sec = t.replace(microsecond=0)
                per_detik[sec] = per_detik.get(sec, 0.0) + (v or 0.0)
        if per_detik:
            out[nama] = sorted((t, round(v, 2)) for t, v in per_detik.items())
    return out


def align_series(series, ref_times):
    """Selaraskan deret [(waktu,nilai)] ke daftar waktu acuan (nilai terdekat)."""
    if not series:
        return [None] * len(ref_times)
    out = []
    for t in ref_times:
        best = min(series, key=lambda s: abs((s[0] - t).total_seconds()))
        out.append(round(best[1], 2) if best[1] is not None else None)
    return out


def events_dari_menit(rows, ambang=AMBANG_SIAGA, jeda_menit=5):
    """
    Kelompokkan menit-menit eksursi (hasil mssql.get_freq_events_day) menjadi
    daftar event. rows: [(menit 'YYYY-MM-DD HH:MM', fmin, fmax)].
    Return list event: {t_ekstrem(datetime), hz_ekstrem, df, arah, kategori,
                        t_mulai, t_selesai}.
    """
    import datetime as _dt
    parsed = []
    for menit, fmin, fmax in rows:
        try:
            t = _dt.datetime.strptime(menit, '%Y-%m-%d %H:%M')
        except (ValueError, TypeError):
            continue
        dev_bawah = NOMINAL_HZ - fmin
        dev_atas  = fmax - NOMINAL_HZ
        if dev_bawah >= dev_atas:
            dev, hz, arah = dev_bawah, fmin, 'turun'
        else:
            dev, hz, arah = dev_atas, fmax, 'naik'
        parsed.append((t, hz, dev, arah))
    parsed.sort(key=lambda x: x[0])

    events, grup = [], []
    def tutup(g):
        if not g:
            return
        t_ek, hz_ek, dev, arah = max(g, key=lambda x: x[2])
        events.append({
            't_ekstrem': t_ek, 'hz_ekstrem': round(hz_ek, 3),
            'df': round(dev, 4), 'arah': arah,
            'kategori': kategori_dari_deviasi(dev),
            't_mulai': g[0][0], 't_selesai': g[-1][0],
        })
    for row in parsed:
        if row[2] < ambang:
            continue
        if grup and (row[0] - grup[-1][0]).total_seconds() > jeda_menit * 60:
            tutup(grup); grup = []
        grup.append(row)
    tutup(grup)
    events.sort(key=lambda e: e['t_ekstrem'], reverse=True)
    return events


def _baseline(series, t_batas):
    """Rata-rata nilai SEBELUM t_batas (kondisi pra-event)."""
    vals = [v for (t, v) in series if v is not None and t < t_batas]
    return round(sum(vals) / len(vals), 2) if vals else None


def _nilai_pada(series, t_target):
    """Nilai pada waktu terdekat t_target."""
    kandidat = [(abs((t - t_target).total_seconds()), v)
                for (t, v) in series if v is not None]
    return round(min(kandidat, key=lambda x: x[0])[1], 2) if kandidat else None


def _waktu_ekstrem(freq):
    """Waktu titik deviasi terbesar dalam deret frekuensi (nadir/puncak)."""
    if not freq:
        return None
    fmax = max(h for _, h in freq)
    fmin = min(h for _, h in freq)
    if (NOMINAL_HZ - fmin) >= (fmax - NOMINAL_HZ):
        return min(freq, key=lambda x: x[1])[0]      # waktu f-min
    return max(freq, key=lambda x: x[1])[0]          # waktu f-max


def _rakit(freq, mw, t_pusat, t0, t1):
    """Rakit dict hasil analisis dari deret freq + mw pada jendela [t0,t1].
    t_pusat = titik acuan baseline/nilai-saat-event (biasanya waktu ekstrem)."""
    df, fmax, fmin = deviasi_maks([h for _, h in freq])
    kategori = kategori_dari_deviasi(df)
    arah = None
    if df is not None:
        arah = 'turun' if (NOMINAL_HZ - (fmin or NOMINAL_HZ)) >= ((fmax or NOMINAL_HZ) - NOMINAL_HZ) else 'naik'

    pembangkit = []
    for nama, series in (mw or {}).items():
        series = sorted([(t, v) for t, v in series if t and v is not None], key=lambda x: x[0])
        if not series:
            continue
        base = _baseline(series, t_pusat) if t_pusat else None
        saat = _nilai_pada(series, t_pusat) if t_pusat else None
        delta = round(saat - base, 2) if (base is not None and saat is not None) else None
        benar = None
        if delta is not None and arah:
            benar = (delta > 0) if arah == 'turun' else (delta < 0)
        pembangkit.append({
            'nama': nama, 'baseline': base, 'saat_event': saat,
            'delta_mw': delta, 'arah_benar': benar, 'series': series,
        })
    pembangkit.sort(key=lambda x: (x['delta_mw'] is None, -(abs(x['delta_mw']) if x['delta_mw'] is not None else 0)))

    return {
        't_pusat': t_pusat, 't0': t0, 't1': t1,
        'freq': freq, 'df': df, 'fmax': fmax, 'fmin': fmin,
        'arah': arah, 'kategori': kategori,
        'warna': KATEGORI_WARNA.get(kategori, '#64748b'),
        'pembangkit': pembangkit,
    }


def _ambil(get_freq, get_mw, t0, t1):
    freq = sorted([(t, h) for t, h in get_freq(t0, t1) if t and h is not None],
                  key=lambda x: x[0])
    return freq, (get_mw(t0, t1) or {})


def analisa_event(t_pusat, get_freq, get_mw, sebelum_detik=60, sesudah_detik=180):
    """Analisis event di sekitar t_pusat (± jendela)."""
    t0 = t_pusat - datetime.timedelta(seconds=sebelum_detik)
    t1 = t_pusat + datetime.timedelta(seconds=sesudah_detik)
    freq, mw = _ambil(get_freq, get_mw, t0, t1)
    return _rakit(freq, mw, t_pusat, t0, t1)


def analisa_rentang(t0, t1, get_freq, get_mw):
    """Analisis untuk RENTANG waktu bebas [t0, t1]. Titik acuan baseline =
    waktu deviasi frekuensi terbesar di dalam rentang."""
    freq, mw = _ambil(get_freq, get_mw, t0, t1)
    t_pusat = _waktu_ekstrem(freq)
    return _rakit(freq, mw, t_pusat, t0, t1)
