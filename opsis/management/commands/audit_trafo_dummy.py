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

PENTING soal GI PALOPO/MAROS/PARE-PARE: 3 dari 4 nama site dummy ini
KEBETULAN sama persis dengan nama GI ASLI yang memang punya trafo
distribusi sungguhan — jadi tidak cukup mengandalkan nama site saja utk
menyimpulkan palsu (beda dgn GI MAKASSAR yg sama sekali tidak ada di
MSSQL). Command ini query MSSQL LANGSUNG saat dijalankan dan membandingkan
tiap (site, bay) yang terdaftar dengan data yang BENAR-BenAR muncul saat
itu — bukan cuma cek nama site atau pola BAY. Trafo yang (site,bay)-nya
TIDAK ada di hasil query live dianggap kandidat hapus; yang cocok
dibiarkan (itu trafo asli). Kalau MSSQL sedang tidak reachable saat
command dijalankan, verifikasi live tidak bisa dilakukan — command akan
berhenti tanpa menghapus apa pun (lebih aman drpd menyimpulkan dari
histori snapshot yg bisa salah).

Jalankan (read-only, aman kapan saja):
    python manage.py audit_trafo_dummy

Hapus entri yang terverifikasi TIDAK ada di MSSQL saat ini (SnapTrafo dulu
baru Trafo, krn FK PROTECT) setelah direview:
    python manage.py audit_trafo_dummy --delete
"""
from django.core.management.base import BaseCommand
from django.db.models import Min, Max, Count

from opsis.models import Trafo, SnapTrafo
from opsis import mssql

DUMMY_SITES = ['GI PALOPO', 'GI MAKASSAR', 'GI MAROS', 'GI PARE-PARE']


class Command(BaseCommand):
    help = 'Audit (dan opsional bersihkan) entri Trafo yang kemungkinan berasal dari fallback dummy MSSQL'

    def add_arguments(self, parser):
        parser.add_argument(
            '--delete', action='store_true',
            help=('Hapus entri yang (site,bay)-nya TIDAK ditemukan di query MSSQL live saat '
                  'command ini dijalankan. Entri yang cocok dgn data live (trafo asli) tidak '
                  'pernah dihapus, walau site-nya ada di daftar dummy.'),
        )

    def handle(self, *args, **options):
        candidates = list(
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

        self.stdout.write('Query MSSQL live untuk verifikasi (site, bay) mana yang benar-benar nyata...')
        live_distribusi = mssql.get_beban_trafo()
        live_ibt = mssql.get_beban_trafo_ibt()

        if (live_distribusi and live_distribusi[0].get('is_dummy')) or (live_ibt and live_ibt[0].get('is_dummy')):
            self.stdout.write(self.style.ERROR(
                'MSSQL sedang TIDAK reachable saat ini — tidak bisa verifikasi live dengan aman. '
                'Coba lagi nanti saat MSSQL sudah tersambung (cek dulu: python manage.py collect_trafo --dry-run).'
            ))
            return

        real_pairs = {(r['site'], r['bay']) for r in live_distribusi + live_ibt}
        self.stdout.write(f'  {len(real_pairs)} pasangan (site,bay) nyata ditemukan di MSSQL saat ini.\n')

        not_found = []
        found = []
        for t in candidates:
            (not_found if (t.site, t.bay) not in real_pairs else found).append(t)

        if found:
            self.stdout.write(self.style.SUCCESS(
                f'== {len(found)} entri COCOK dengan MSSQL live — trafo ASLI, tidak akan disentuh =='
            ))
            for t in found:
                self.stdout.write(f'  [{t.id}] {t.site} — {t.bay} | {t.snap_count} snapshot')

        if not_found:
            self.stdout.write(self.style.WARNING(
                f'\n== {len(not_found)} entri TIDAK DITEMUKAN di MSSQL live — kandidat PALSU =='
            ))
            for t in not_found:
                self.stdout.write(
                    f'  [{t.id}] {t.site} — {t.bay} | aktif={t.aktif} | '
                    f'{t.snap_count} snapshot | {t.first_seen} s/d {t.last_seen}'
                )
        else:
            self.stdout.write(self.style.SUCCESS('\nTidak ada entri yang tidak ditemukan di MSSQL. Aman.'))
            return

        if not options.get('delete'):
            self.stdout.write(self.style.WARNING(
                '\nJalankan ulang dengan --delete untuk hapus entri di atas beserta seluruh histori SnapTrafo-nya.'
            ))
            return

        self.stdout.write(self.style.ERROR(f'\nMenghapus {len(not_found)} entri...'))
        for t in not_found:
            tid, site, bay = t.id, t.site, t.bay  # simpan sebelum delete() — id di-clear jadi None setelahnya
            deleted_snaps, _ = SnapTrafo.objects.filter(trafo=t).delete()
            t.delete()
            self.stdout.write(f'  Dihapus: [{tid}] {site} — {bay} ({deleted_snaps} snapshot ikut terhapus)')
        self.stdout.write(self.style.SUCCESS(f'Selesai — {len(not_found)} entri Trafo dummy dihapus.'))
