#!/usr/bin/env python3
"""
Contoh klien API Eksternal FASOP — ambil data OPSIS.

Hanya pustaka standar Python (tanpa `pip install`). Panduan lengkap tiap
endpoint: docs/API_EKSTERNAL.md.

Pakai:
    export FASOP_URL=https://<domain-fasop>
    export FASOP_API_KEY=<kunci dari Admin → Devices → Kunci API>
    python3 contoh_klien_opsis.py

Kunci dibaca dari environment, BUKAN ditulis di skrip — perlakukan seperti
password. Kunci itu hanya membuka data yang dicentangkan admin untuknya; data
lain dibalas 403 dengan pesan yang menyebut alasannya.
"""
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

BASE = os.environ.get('FASOP_URL', 'https://fasop.example').rstrip('/') + '/api/v1/'
KUNCI = os.environ.get('FASOP_API_KEY', '')


class DataTidakTersedia(Exception):
    """503 — historian SCADA tidak terjangkau. Lewati putaran ini, JANGAN isi 0."""


def ambil(path, **params):
    """GET satu endpoint, kembalikan dict JSON-nya."""
    url = BASE + path
    if params:
        url += '?' + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={'X-API-Key': KUNCI})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as e:
        # FASOP selalu membalas JSON berisi `message`, termasuk saat menolak.
        try:
            pesan = json.load(e).get('message', '')
        except ValueError:
            pesan = ''
        if e.code == 503:
            raise DataTidakTersedia(pesan) from None
        raise RuntimeError(f'HTTP {e.code} dari {path}: {pesan}') from None


def main():
    if not KUNCI:
        sys.exit('Isi FASOP_API_KEY dulu.')

    # 1. Beban pembangkit terkini (?unit=0 = tanpa rincian per unit, lebih ringan)
    try:
        kit = ambil('opsis/beban-pembangkit/', unit=0)
        print(f"[{kit['waktu']}] Total {kit['total_mw']} MW, "
              f"{kit['frekuensi_sistem']} Hz, {kit['jumlah']} pembangkit")
        for p in kit['pembangkit']:
            tanda = '  ⚠ diragukan: ' + p['keterangan'] if p['diragukan'] else ''
            print(f"  {p['kode']:<12} {p['nama']:<28} {p['mw']} MW{tanda}")
    except DataTidakTersedia as e:
        print('Beban pembangkit dilewati:', e)

    # 2. Beban KTT terkini
    try:
        ktt = ambil('opsis/beban-ktt/')
        print(f"\nBeban KTT total {ktt['total_mw']} MW")
        for k in ktt['konsumen']:
            print(f"  {k['kode']:<12} {k['nama']:<20} {k['mw']} MW")
    except DataTidakTersedia as e:
        print('Beban KTT dilewati:', e)

    # 3. Frekuensi per detik, bawaan 60 menit terakhir (atau dari=/sampai= ISO,
    #    maks. 6 jam). Endpoint rentang tidak 503: rentang sepi = `deret: []`.
    hz = ambil('opsis/frekuensi/')
    deret = [d['hz'] for d in hz['deret'] if d['hz'] is not None]
    if deret:
        print(f"\nFrekuensi 60 menit: min {min(deret):.3f} / maks {max(deret):.3f} Hz "
              f"({hz['sumber_teks']})")
    else:
        print('\nFrekuensi: tidak ada data di rentang ini.')

    # 4. Riwayat per menit satu pembangkit (maks. 3 hari per permintaan)
    #    riwayat = ambil('opsis/beban-pembangkit/riwayat/',
    #                    kode='BAKARU', dari='2026-11-06T08:00', sampai='2026-11-06T12:00')


if __name__ == '__main__':
    try:
        main()
    except RuntimeError as e:      # 401/403/400/404 — baca pesannya
        sys.exit(str(e))
