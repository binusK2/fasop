"""
Step 2 dari 2 — Apply rencana rename nama perangkat dari CSV.

Jalankan (dry-run terlebih dahulu!):
    python manage.py apply_rename_plan rename_plan.csv
    python manage.py apply_rename_plan rename_plan.csv --apply
    python manage.py apply_rename_plan rename_plan.csv --apply --log rename_log.csv

Kolom CSV wajib: id, nama_lama, nama_usulan, status
Baris dengan status OK atau SKIP dilewati.
Baris dengan status REVIEW dilewati kecuali nama_usulan sudah diubah manual.

Default: dry-run (tidak ada perubahan ke DB). Tambahkan --apply untuk eksekusi.
"""
import csv
import sys
from datetime import datetime
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from devices.models import Device


class Command(BaseCommand):
    help = 'Apply rencana rename dari CSV (Step 2). Gunakan --apply untuk eksekusi.'

    def add_arguments(self, parser):
        parser.add_argument(
            'csv_file',
            help='Path ke file CSV hasil generate_rename_plan (yang sudah direview)',
        )
        parser.add_argument(
            '--apply', action='store_true',
            help='Eksekusi perubahan ke database. Tanpa flag ini: dry-run saja.',
        )
        parser.add_argument(
            '--log', default=None,
            help='Path file CSV untuk log hasil rename (default: stdout)',
        )
        parser.add_argument(
            '--skip-review', action='store_true',
            help='Lewati baris REVIEW (tidak ubah). Default sudah lewati REVIEW.',
        )
        parser.add_argument(
            '--include-review', action='store_true',
            help='Proses baris REVIEW (yang nama_usulan sudah diubah manual).',
        )

    def handle(self, *args, **options):
        csv_path  = options['csv_file']
        do_apply  = options['apply']
        log_path  = options['log']
        inc_review = options['include_review']

        # ── Baca CSV ─────────────────────────────────────────────────
        try:
            with open(csv_path, newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                rows = list(reader)
        except FileNotFoundError:
            raise CommandError(f'File tidak ditemukan: {csv_path}')
        except Exception as e:
            raise CommandError(f'Gagal membaca CSV: {e}')

        required_cols = {'id', 'nama_lama', 'nama_usulan', 'status'}
        if rows and not required_cols.issubset(set(rows[0].keys())):
            missing = required_cols - set(rows[0].keys())
            raise CommandError(f'Kolom CSV kurang: {missing}')

        # ── Filter baris yang perlu diproses ─────────────────────────
        to_process = []
        skipped_ok   = 0
        skipped_skip = 0
        skipped_rev  = 0
        skipped_same = 0

        for row in rows:
            status       = row.get('status', '').strip().upper()
            nama_lama    = row.get('nama_lama', '').strip()
            nama_usulan  = row.get('nama_usulan', '').strip()

            if status in ('OK', ''):
                skipped_ok += 1
                continue
            if status == 'SKIP':
                skipped_skip += 1
                continue
            if status == 'REVIEW' and not inc_review:
                skipped_rev += 1
                continue
            if nama_lama == nama_usulan:
                skipped_same += 1
                continue
            if not nama_usulan:
                skipped_same += 1
                continue

            try:
                device_id = int(row['id'])
            except (ValueError, KeyError):
                self.stderr.write(f'  WARN: id tidak valid di baris: {row}')
                continue

            to_process.append({
                'id':          device_id,
                'nama_lama':   nama_lama,
                'nama_usulan': nama_usulan,
                'status':      status,
                'jenis':       row.get('jenis', ''),
                'lokasi':      row.get('lokasi', ''),
            })

        self.stderr.write(f'\n  CSV    : {csv_path}')
        self.stderr.write(f'  Baris  : {len(rows)} total')
        self.stderr.write(f'  OK     : {skipped_ok} dilewati (sudah sesuai)')
        self.stderr.write(f'  SKIP   : {skipped_skip} dilewati (jenis tidak ditangani)')
        self.stderr.write(f'  REVIEW : {skipped_rev} dilewati (belum diedit)')
        self.stderr.write(f'  Sama   : {skipped_same} dilewati (nama_usulan tidak berubah)')
        self.stderr.write(f'  Proses : {len(to_process)} akan direname\n')

        if not to_process:
            self.stderr.write('  Tidak ada yang perlu direname. Selesai.\n')
            return

        # ── Validasi: cek bahwa id & nama_lama masih cocok di DB ─────
        ids = [r['id'] for r in to_process]
        db_map = {
            d.pk: d
            for d in Device.objects.filter(pk__in=ids, is_deleted=False)
        }

        valid_rows   = []
        invalid_rows = []

        for row in to_process:
            db_dev = db_map.get(row['id'])
            if db_dev is None:
                invalid_rows.append({**row, 'error': 'ID tidak ditemukan di DB'})
                continue
            if db_dev.nama != row['nama_lama']:
                invalid_rows.append({
                    **row,
                    'error': f'Nama DB saat ini: "{db_dev.nama}" ≠ nama_lama CSV: "{row["nama_lama"]}"',
                })
                continue
            row['_device'] = db_dev
            valid_rows.append(row)

        if invalid_rows:
            self.stderr.write(f'  WARN: {len(invalid_rows)} baris tidak valid (skip):')
            for r in invalid_rows[:10]:
                self.stderr.write(f'    id={r["id"]} — {r["error"]}')
            if len(invalid_rows) > 10:
                self.stderr.write(f'    ... dan {len(invalid_rows) - 10} lainnya')
            self.stderr.write('')

        if not valid_rows:
            self.stderr.write('  Tidak ada baris valid untuk diproses. Selesai.\n')
            return

        # ── Dry-run preview ───────────────────────────────────────────
        mode_label = 'APPLY' if do_apply else 'DRY-RUN'
        self.stderr.write(f'  Mode: {mode_label}')
        if not do_apply:
            self.stderr.write('  (Tidak ada perubahan ke DB. Tambahkan --apply untuk eksekusi.)\n')

        preview_count = min(20, len(valid_rows))
        self.stderr.write(f'  Preview {preview_count} dari {len(valid_rows)} rename:')
        for r in valid_rows[:preview_count]:
            self.stderr.write(f'    [{r["id"]}] "{r["nama_lama"]}"')
            self.stderr.write(f'          → "{r["nama_usulan"]}"')
        if len(valid_rows) > preview_count:
            self.stderr.write(f'    ... dan {len(valid_rows) - preview_count} lainnya')
        self.stderr.write('')

        if not do_apply:
            return

        # ── Apply dalam satu transaksi ────────────────────────────────
        log_rows = []
        applied  = 0
        errors   = []

        try:
            with transaction.atomic():
                for row in valid_rows:
                    dev = row['_device']
                    old_name = dev.nama
                    dev.nama = row['nama_usulan']
                    try:
                        dev.save(update_fields=['nama'])
                        applied += 1
                        log_rows.append({
                            'id':         dev.pk,
                            'jenis':      row['jenis'],
                            'lokasi':     row['lokasi'],
                            'nama_lama':  old_name,
                            'nama_baru':  dev.nama,
                            'status':     'RENAMED',
                            'waktu':      datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        })
                    except Exception as e:
                        errors.append({'id': dev.pk, 'error': str(e)})
                        log_rows.append({
                            'id':         dev.pk,
                            'jenis':      row['jenis'],
                            'lokasi':     row['lokasi'],
                            'nama_lama':  old_name,
                            'nama_baru':  row['nama_usulan'],
                            'status':     f'ERROR: {e}',
                            'waktu':      datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        })

                if errors:
                    raise CommandError(
                        f'{len(errors)} error saat rename. Transaksi dibatalkan. '
                        f'Cek log untuk detail.'
                    )

        except CommandError:
            raise
        except Exception as e:
            raise CommandError(f'Transaksi gagal dan dibatalkan: {e}')

        # ── Tulis log ─────────────────────────────────────────────────
        log_out = open(log_path, 'w', newline='', encoding='utf-8') \
                  if log_path else sys.stdout

        log_writer = csv.DictWriter(log_out, fieldnames=[
            'id', 'jenis', 'lokasi', 'nama_lama', 'nama_baru', 'status', 'waktu'
        ])
        log_writer.writeheader()
        log_writer.writerows(log_rows)

        if log_path:
            log_out.close()

        # ── Summary ───────────────────────────────────────────────────
        self.stderr.write(f'  ✓ Selesai: {applied} perangkat direname.')
        if log_path:
            self.stderr.write(f'  Log ditulis ke: {log_path}')
        self.stderr.write('')
