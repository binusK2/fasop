"""
Serialisasi aset, lokasi, dan pemeliharaan untuk endpoint baca
`/api/v1/fasop/aset/`, `/api/v1/fasop/lokasi/`, dan
`/api/v1/fasop/pemeliharaan/riwayat/`.

Konsumen pertamanya Fasop Induk — dashboard UIP3B yang MENYALIN data FASOP ke
PostgreSQL-nya sendiri secara berkala. Karena itu bentuknya berbeda dari
endpoint `fasop/peralatan/` dan `fasop/pemeliharaan/` yang dibuat untuk bot
WhatsApp (ringkas, maks 20/30 baris, tanpa ID):

  * Setiap baris punya `id` (hashid, sama dengan yang dipakai URL FASOP) supaya
    penyalin bisa meng-upsert dan mendeteksi baris yang hilang.
  * Semua daftar berhalaman dan diurutkan `pk`, jadi menarik halaman 1..n
    selalu menghasilkan himpunan yang sama selama datanya tidak berubah.
  * Hasil pengukuran dikirim GENERIK dari tabel detailnya, lengkap dengan skema
    kolomnya. Ada 20 tabel detail (satu per jenis peralatan) dan jumlahnya terus
    bertambah — Master Station baru saja dipakai untuk VM SCADA. Kalau tiap
    tabel dipetakan tangan di sini, tabel ke-21 akan diam-diam tidak pernah
    terkirim. Dengan membaca relasi OneToOne `Maintenance` langsung, tabel baru
    otomatis ikut (dijaga tes).
"""
import datetime
from decimal import Decimal

from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone

from fasop.hashids_helper import encode

PREFIX_DETAIL = 'Maintenance'

# Kolom yang tidak pernah dikirim, apa pun tabelnya.
#   public_token : membuka halaman publik QR tanpa login — itu kunci, bukan data.
#   wiring_json  : data mentah editor wiring diagram, bisa ratusan KB per
#                  perangkat dan tidak berarti apa-apa di luar editornya.
#   komponen_relokasi_ids : pk integer mentah DeviceComponent; di luar FASOP
#                  angka itu tidak menunjuk apa pun (ID yang dikirim hashid).
KOLOM_TIDAK_DIKIRIM = {'public_token', 'wiring_json', 'komponen_relokasi_ids'}


# ── Nilai dasar ─────────────────────────────────────────────────────────────
def waktu_lokal(dt):
    if dt is None:
        return None
    if timezone.is_aware(dt):
        dt = timezone.localtime(dt)
    return dt.isoformat()


def url_berkas(berkas):
    """URL relatif /media/... sebuah FileField, atau None bila kosong."""
    if not berkas:
        return None
    try:
        return berkas.url
    except ValueError:
        return None


def nama_user(u):
    if u is None:
        return None
    return u.get_full_name() or u.username


def label_objek(obj):
    if isinstance(obj, User):
        return nama_user(obj)
    return str(obj)


def pelaksana(m):
    """Nama pelaksana sebuah pemeliharaan — aturan yang sama dengan ekspor
    Excel (`maintenance/catu_daya.py::_pelaksana`): akun FASOP yang dicentang
    lebih dulu, baru nama yang diketik bebas. Butuh prefetch `technicians`."""
    nama = [nama_user(t) for t in m.technicians.all()]
    if not nama:
        nama = [str(n) for n in (m.pelaksana_names or []) if n]
    return nama


# ── Serialisasi generik sebuah baris model ──────────────────────────────────
_TIPE = (
    (models.BooleanField, 'boolean'),
    (models.DecimalField, 'desimal'),
    (models.FloatField, 'desimal'),
    (models.IntegerField, 'bulat'),      # termasuk PositiveSmallIntegerField dkk.
    (models.DateTimeField, 'waktu'),     # sebelum DateField: DateTimeField turunannya
    (models.DateField, 'tanggal'),
    (models.TimeField, 'jam'),
    (models.JSONField, 'json'),
    (models.FileField, 'berkas'),        # termasuk ImageField
    (models.ForeignKey, 'relasi'),
)


def tipe_kolom(f):
    for kelas, nama in _TIPE:
        if isinstance(f, kelas):
            return nama
    return 'teks'


def kolom_dikirim(Model, kecuali=()):
    """Field konkret yang dikirim: tanpa pk, tanpa FK ke induknya (`kecuali`),
    dan tanpa KOLOM_TIDAK_DIKIRIM."""
    buang = set(kecuali) | KOLOM_TIDAK_DIKIRIM
    return [f for f in Model._meta.concrete_fields
            if not f.primary_key and f.name not in buang]


def fk_dikirim(Model, kecuali=()):
    """Nama FK yang ikut dikirim — untuk select_related, supaya label relasinya
    tidak memicu satu query per baris."""
    return [f.name for f in kolom_dikirim(Model, kecuali) if f.is_relation]


def nilai_kolom(obj, f):
    if isinstance(f, models.FileField):
        return url_berkas(getattr(obj, f.name))
    if f.is_relation:
        if getattr(obj, f.attname) is None:
            return None
        try:
            rel = getattr(obj, f.name)
        except f.related_model.DoesNotExist:   # FK menggantung
            return None
        return {'id': encode(rel.pk), 'label': label_objek(rel)}
    v = f.value_from_object(obj)
    if isinstance(v, datetime.datetime):
        return waktu_lokal(v)
    if isinstance(v, (datetime.date, datetime.time)):
        return v.isoformat()
    if isinstance(v, Decimal):
        return float(v)
    return v


def baris(obj, kecuali=()):
    """Semua kolom konkret sebuah objek sebagai dict {nama_field: nilai}."""
    return {f.name: nilai_kolom(obj, f) for f in kolom_dikirim(type(obj), kecuali)}


def skema(Model, kecuali=()):
    """Keterangan tiap kolom: label (verbose_name), tipe, dan pilihan bila ada.

    `pilihan` memetakan nilai yang tersimpan ke teks yang tampil di layar FASOP
    (mis. "ok" -> "OK / Normal"), jadi penerima tidak perlu menyalin daftar
    choices dari kode FASOP."""
    hasil = []
    for f in kolom_dikirim(Model, kecuali):
        k = {'nama': f.name, 'label': str(f.verbose_name), 'tipe': tipe_kolom(f)}
        if f.choices:
            k['pilihan'] = {str(a): str(b) for a, b in f.flatchoices}
        hasil.append(k)
    return hasil


# ── Tabel hasil pengukuran ──────────────────────────────────────────────────
def tabel_detail():
    """
    [(kode, Model)] seluruh tabel hasil pemeliharaan: setiap model
    `Maintenance*` yang ber-OneToOne ke Maintenance (PLC, Router, ...,
    Corrective, Master Station).

    `FormOffline` juga OneToOne ke Maintenance tapi bukan hasil pengukuran
    (berkas form kertas yang diunggah), jadi tersaring oleh prefix namanya.
    """
    from maintenance.models import Maintenance
    hasil = []
    for rel in Maintenance._meta.related_objects:
        M = rel.related_model
        if rel.one_to_one and M.__name__.startswith(PREFIX_DETAIL):
            hasil.append((M.__name__[len(PREFIX_DETAIL):].lower(), M))
    return hasil


def skema_tabel(kode_dipakai=None):
    """{kode: {nama, kolom}} untuk tabel di `kode_dipakai` (None = semua)."""
    return {
        kode: {'nama': str(M._meta.verbose_name), 'kolom': skema(M, kecuali=('maintenance',))}
        for kode, M in tabel_detail()
        if kode_dipakai is None or kode in kode_dipakai
    }


def hasil_pengukuran(maintenance_ids):
    """
    {maintenance_id: [{'tabel': kode, 'data': {...}}]} untuk sekumpulan id.

    Satu query per tabel detail (20), bukan per pemeliharaan, dan bukan satu
    JOIN raksasa: jumlah kolom ke-20 tabel itu lebih dari 1.000.

    Biasanya satu pemeliharaan punya satu tabel, tapi Corrective bisa punya
    `corrective` DAN tabel jenis peralatannya — karena itu nilainya list.
    """
    ids = list(maintenance_ids)
    hasil = {i: [] for i in ids}
    if not ids:
        return hasil
    for kode, M in tabel_detail():
        qs = M.objects.filter(maintenance_id__in=ids)
        fk = fk_dikirim(M, kecuali=('maintenance',))
        if fk:
            qs = qs.select_related(*fk)
        for obj in qs:
            hasil[obj.maintenance_id].append(
                {'tabel': kode, 'data': baris(obj, kecuali=('maintenance',))})
    return hasil


# ── Lokasi ──────────────────────────────────────────────────────────────────
def peta_lokasi():
    """
    {nama_lokasi: {'id', 'branch', 'ultg'}} dari master SiteLocation.

    `Device.lokasi` teks bebas yang harus sama persis dengan
    `SiteLocation.nama`; dicocokkan setelah strip(), sama seperti peta & daftar
    lokasi di devices/views.py. Satu lokasi bisa dibawahi lebih dari satu ULTG
    (M2M), jadi `ultg` list.
    """
    from devices.models import SiteLocation
    peta = {}
    for sl in SiteLocation.objects.select_related('branch').prefetch_related('ultg_set'):
        peta[sl.nama.strip()] = {
            'id':     encode(sl.pk),
            'branch': sl.branch.nama if sl.branch else None,
            'ultg':   sorted(u.nama for u in sl.ultg_set.all()),
        }
    return peta


# ── Aset ────────────────────────────────────────────────────────────────────
def aset(d, peta, tahun_ini):
    """Satu Device sebagai baris aset. Butuh select_related('jenis', 'host')."""
    lok = peta.get((d.lokasi or '').strip())
    return {
        'id':                   encode(d.pk),
        'nama':                 d.nama,
        'asset_id':             d.asset_id or None,
        'status_aset':          d.status_aset,
        'status_aset_label':    d.get_status_aset_display(),
        'jenis':                d.jenis.name if d.jenis else None,
        'merk':                 d.merk,
        'tipe':                 d.type or None,
        'serial_number':        d.serial_number or None,
        'firmware_version':     d.firmware_version or None,
        'ip_address':           d.ip_address or None,
        'lokasi':               d.lokasi,
        'lokasi_id':            lok['id'] if lok else None,
        'branch':               lok['branch'] if lok else None,
        'ultg':                 lok['ultg'] if lok else [],
        'status_operasi':       d.status_operasi,
        'status_operasi_label': d.get_status_operasi_display(),
        'tahun_operasi':        d.tahun_operasi,
        'umur_tahun':           (tahun_ini - d.tahun_operasi) if d.tahun_operasi else None,
        'host':                 {'id': encode(d.host_id), 'nama': d.host.nama} if d.host_id else None,
        'keterangan':           d.keterangan or None,
        'spesifikasi':          d.spesifikasi or {},
        'foto':                 [u for u in (url_berkas(d.foto), url_berkas(d.foto2)) if u],
        'dibuat_pada':          waktu_lokal(d.created_at),
    }


def health_index(d, configs, rinci=False):
    """Skor HI yang sama dengan halaman Health Index (dihitung, tidak disimpan).

    Satu perangkat yang gagal dihitung (data setengah jadi) tidak boleh
    menjatuhkan seluruh halaman — ia tampil dengan HI None, sama seperti
    `fasop/peralatan/`."""
    from health_index.calculator import calculate_hi
    try:
        hi = calculate_hi(d, save_snapshot=False, configs=configs)
    except Exception:
        return {'health_index': None, 'kategori_hi': None}
    hasil = {'health_index': hi['score'], 'kategori_hi': hi['kategori']['label']}
    if rinci:
        hasil['rincian_hi'] = [
            {
                'faktor':     b.get('faktor'),
                'nilai':      b.get('nilai'),
                'keterangan': b.get('keterangan'),
                'deduksi':    b.get('deduksi'),
                'maks':       b.get('maks'),
                'status':     b.get('status'),
            }
            for b in hi['breakdown']
        ]
        hasil['jumlah_pemeliharaan'] = hi['total_maintenance']
        hasil['jumlah_gangguan'] = hi['total_gangguan']
    return hasil


# ── Pemeliharaan ────────────────────────────────────────────────────────────
def pemeliharaan(m):
    """Satu Maintenance sebagai baris riwayat. Butuh select_related
    ('device', 'device__jenis', 'signed_by') + prefetch_related('technicians')."""
    d = m.device
    return {
        'id':         encode(m.pk),
        'peralatan': {
            'id':       encode(d.pk),
            'nama':     d.nama,
            'asset_id': d.asset_id or None,
            'jenis':    d.jenis.name if d.jenis else None,
            'lokasi':   d.lokasi,
        },
        'tipe':        m.maintenance_type,
        'status':      m.status,
        'tanggal':     waktu_lokal(m.date),
        'deskripsi':   m.description or '',
        'pelaksana':   pelaksana(m),
        'ttd': {
            'sudah': m.signed_by_id is not None,
            'oleh':  nama_user(m.signed_by),
            'pada':  waktu_lokal(m.signed_at),
        },
        'catatan_am':  m.catatan_am or '',
        'foto':        url_berkas(m.photo),
        'dibuat_pada': waktu_lokal(m.created_at),
    }
