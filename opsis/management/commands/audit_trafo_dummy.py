"""
Management command: audit_trafo_dummy

Laporkan (dan opsional bersihkan) entri Trafo yang kemungkinan besar
ke-auto-daftar dari data DUMMY MSSQL, bukan trafo asli — lihat
opsis.mssql._dummy_beban_trafo()/_dummy_beban_trafo_ibt() (4 nama site
fallback: GI PALOPO, GI MAKASSAR, GI MAROS, GI PARE-PARE) dan
opsis.views._trafo_aktif_saja() (auto-registrasi Trafo baru).

Fix di kode (mssql.py menandai baris dummy dengan 'is_dummy': True,
_trafo_aktif_saja() menolaknya) MENCEGAH pencemaran BARU sejak command ini
dibuat — tapi Trafo/SnapTrafo yang SUDAH terlanjur tersimpan sebelum fix
ini di-deploy tidak otomatis hilang, makanya command ini ada.

PENTING soal keandalan deteksi:
  - Untuk trafo IBT (BAY TRF65%/TRF54%): GI PALOPO/MAKASSAR/MAROS/PARE-PARE
    TIDAK memiliki instalasi IBT asli (diverifikasi lewat query MSSQL
    langsung) — jadi entri IBT di 4 site ini bisa disimpulkan PALSU dengan
    keyakinan tinggi, aman dihapus otomatis lewat --delete-ibt.
  - Untuk trafo DISTRIBUSI (BAY TRF52%/TRF42%): GI PALOPO/MAROS/PARE-PARE
    ADALAH GI ASLI dengan trafo distribusi sungguhan — nama site dummy
    KEBETULAN tumpang tindih dengan nama GI nyata. Command ini TIDAK
    menghapus entri distribusi secara otomatis; hanya melaporkannya supaya
    dicek manual (bandingkan BAY yang terdaftar dengan BAY asli di lapangan
    lewat Django Admin).

Jalankan (read-only, aman kapan saja):
    python manage.py audit_trafo_dummy

Hapus entri IBT palsu di 4 site tsb (SnapTrafo dulu baru Trafo, krn FK
PROTECT) setelah direview:
    python manage.py audit_trafo_dummy --delete-ibt
"""
from django.core.management.base import BaseCommand
from django.db.models import Q, Min, Max, Count

from opsis.models import Trafo, SnapTrafo

DUMMY_SITES = ['GI PALOPO', 'GI MAKASSAR', 'GI MAROS', 'GI PARE-PARE']


class Command(BaseCommand):
    help = 'Audit (dan opsional bersihkan) entri Trafo yang kemungkinan berasal dari fallback dummy MSSQL'

    def add_arguments(self, parser):
        parser.add_argument(
            '--delete-ibt', action='store_true',
            help=('Hapus entri IBT (BAY TRF65%%/TRF54%%) di 4 site dummy — GI ini tidak '
                  'punya instalasi IBT asli, aman dihapus otomatis. Entri distribusi TIDAK '
                  'pernah dihapus otomatis oleh command ini.'),
        )

    def handle(self, *args, **options):
        candidates = (
            Trafo.objects
            .filter(site__in=DUMMY_SITES)
            .annotate(
                snap_count=Count('snaps'),
                first_seen=Min('snaps__waktu'),
                last_seen=Max('snaps__waktu'),
            )
            .order_by('site', 'bay')
        )

        if not candidates:
            self.stdout.write('Tidak ada entri Trafo di 4 site dummy (GI PALOPO/MAKASSAR/MAROS/PARE-PARE). Aman.')
            return

        ibt_rows = []
        distribusi_rows = []
        for t in candidates:
            is_ibt = t.bay.upper().startswith('TRF65') or t.bay.upper().startswith('TRF54')
            (ibt_rows if is_ibt else distribusi_rows).append(t)

        if ibt_rows:
            self.stdout.write(self.style.WARNING(
                f'\n== {len(ibt_rows)} entri IBT di site dummy — GI ini TIDAK punya IBT asli, kemungkinan besar PALSU =='
            ))
            for t in ibt_rows:
                self.stdout.write(
                    f'  [{t.id}] {t.site} — {t.bay} | aktif={t.aktif} | '
                    f'{t.snap_count} snapshot | {t.first_seen} s/d {t.last_seen}'
                )

        if distribusi_rows:
            self.stdout.write(self.style.NOTICE(
                f'\n== {len(distribusi_rows)} entri DISTRIBUSI di site dummy — site ini ASLI ada di lapangan, '
                'CEK MANUAL per-bay (bandingkan dgn Django Admin / data lapangan), TIDAK dihapus otomatis =='
            ))
            for t in distribusi_rows:
                self.stdout.write(
                    f'  [{t.id}] {t.site} — {t.bay} | aktif={t.aktif} | '
                    f'{t.snap_count} snapshot | {t.first_seen} s/d {t.last_seen}'
                )

        if not options.get('delete_ibt'):
            if ibt_rows:
                self.stdout.write(self.style.WARNING(
                    '\nJalankan ulang dengan --delete-ibt untuk hapus entri IBT palsu di atas '
                    '(beserta seluruh histori SnapTrafo-nya).'
                ))
            return

        if not ibt_rows:
            self.stdout.write('\n--delete-ibt: tidak ada entri IBT dummy untuk dihapus.')
            return

        self.stdout.write(self.style.ERROR(f'\nMenghapus {len(ibt_rows)} entri IBT dummy...'))
        for t in ibt_rows:
            tid, site, bay = t.id, t.site, t.bay  # simpan sebelum delete() — id di-clear jadi None setelahnya
            deleted_snaps, _ = SnapTrafo.objects.filter(trafo=t).delete()
            t.delete()
            self.stdout.write(f'  Dihapus: [{tid}] {site} — {bay} ({deleted_snaps} snapshot ikut terhapus)')
        self.stdout.write(self.style.SUCCESS(f'Selesai — {len(ibt_rows)} entri Trafo IBT dummy dihapus.'))
