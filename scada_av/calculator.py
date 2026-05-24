"""
Django wrapper untuk spectrum7_av (library kalkulasi SCADA Availability).

Entry point utama: run_full_calculation(session_id)
"""
import logging
import time
from io import BytesIO
from typing import Dict

logger = logging.getLogger(__name__)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _td_seconds(td) -> float:
    """Timedelta → float seconds, aman jika None/NaT."""
    try:
        return float(td.total_seconds())
    except Exception:
        return 0.0


def _safe_int(val) -> int:
    try:
        return int(val)
    except Exception:
        return 0


def _safe_float(val) -> float:
    try:
        return float(val)
    except Exception:
        return 0.0


def _build_file_dict(session) -> Dict[str, BytesIO]:
    """Baca semua file yang diupload ke session dan kembalikan sebagai Dict[filename, BytesIO]."""
    file_dict = {}
    for av_file in session.files.all():
        av_file.file.open('rb')
        file_dict[av_file.filename] = BytesIO(av_file.file.read())
        av_file.file.close()
    return file_dict


# ── Core calculation calls ────────────────────────────────────────────────────

def run_rtu(file_dict: Dict[str, BytesIO], start_date, end_date, master: str = 'spectrum'):
    """
    Jalankan kalkulasi RTU Availability menggunakan spectrum7_av core.

    Args:
        file_dict : {filename: BytesIO}
        start_date, end_date : range periode (date atau datetime)
        master     : 'spectrum' | 'survalent'

    Returns:
        AvRTUResult  — hasil kalkulasi RTU
    """
    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    from spectrum7_av.core.rtu import RTU, RTUConfig
    from spectrum7_av.core.soe import SOE

    config = RTUConfig(master=master)
    av = RTU(config)

    # Baca sebagai SOE file; fallback ke AVRS jika kosong
    df_soe = av.read_soe_file(file_dict)
    if df_soe is not None and hasattr(df_soe, '__len__') and len(df_soe) > 0:
        soe_data = SOE(data=df_soe, config=config, sources=av.reader.sources).data
        av.analyze_soe(soe_data)
    else:
        # File AVRS (RTU preprocessed) — baca langsung
        for f in file_dict.values():
            f.seek(0)
        av.read_file(file_dict)

    return av.calculate(start_date=start_date, end_date=end_date)


def run_rcd(file_dict: Dict[str, BytesIO], start_date, end_date, master: str = 'spectrum'):
    """
    Jalankan kalkulasi RCD Success Rate.

    Returns:
        AvRCDResult — hasil kalkulasi RCD
    """
    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    from spectrum7_av.core.rcd import RCD, RCDConfig
    from spectrum7_av.core.soe import SOE

    config = RCDConfig(master=master)
    av = RCD(config)

    df_soe = av.read_soe_file(file_dict)
    if df_soe is not None and hasattr(df_soe, '__len__') and len(df_soe) > 0:
        soe_data = SOE(data=df_soe, config=config, sources=av.reader.sources).data
        av.analyze_soe(soe_data)
    else:
        for f in file_dict.values():
            f.seek(0)
        av.read_file(file_dict)

    return av.calculate(start_date=start_date, end_date=end_date)


# ── DB save helpers ───────────────────────────────────────────────────────────

def _save_rtu_results(session, result) -> int:
    from .models import RtuAvResult

    if result is None or result.data is None:
        return 0

    df_av = result.data.availability
    if df_av is None or df_av.empty:
        return 0

    objs = []
    for _, row in df_av.iterrows():
        objs.append(RtuAvResult(
            session             = session,
            rtu                 = str(row.get('rtu', '')),
            long_name           = str(row.get('long_name', '')),
            downtime_occurences = _safe_int(row.get('downtime_occurences', 0)),
            total_downtime_s    = _td_seconds(row.get('total_downtime')),
            rtu_downtime_s      = _td_seconds(row.get('rtu_downtime')),
            link_downtime_s     = _td_seconds(row.get('link_downtime')),
            other_downtime_s    = _td_seconds(row.get('other_downtime')),
            unclassified_dt_s   = _td_seconds(row.get('unclassified_downtime')),
            time_range_s        = _td_seconds(row.get('time_range')),
            rtu_availability    = _safe_float(row.get('rtu_availability', 0)),
            link_availability   = _safe_float(row.get('link_availability', 0)),
            overall             = _safe_float(row.get('overall', 0)),
        ))

    RtuAvResult.objects.bulk_create(objs)
    return len(objs)


def _save_rcd_results(session, result):
    from .models import RcdSummary, RcdBayResult

    if result is None:
        return

    RcdSummary.objects.update_or_create(
        session=session,
        defaults=dict(
            total_count         = _safe_int(result.total_count),
            total_valid         = _safe_int(result.total_valid),
            total_success       = _safe_int(result.total_success),
            total_failed        = _safe_int(result.total_failed),
            total_reps          = _safe_int(result.total_reps),
            total_marked_unused = _safe_int(result.total_marked_unused),
            success_ratio       = _safe_float(result.success_ratio),
            success_close_ratio = _safe_float(result.success_close_ratio),
            success_open_ratio  = _safe_float(result.success_open_ratio),
        )
    )

    # Per-bay results
    df_bay = result.data.bay
    if df_bay is not None and not df_bay.empty:
        objs = []
        for _, row in df_bay.iterrows():
            objs.append(RcdBayResult(
                session      = session,
                station      = str(row.get('b1', '')),
                bay_b2       = str(row.get('b2', '')),
                bay_b3       = str(row.get('b3', '')),
                occurences   = _safe_int(row.get('occurences', 0)),
                success      = _safe_int(row.get('success', 0)),
                failed       = _safe_int(row.get('failed', 0)),
                success_rate = _safe_float(row.get('success_rate', 0)),
                open_success = _safe_int(row.get('open_success', 0)),
                open_failed  = _safe_int(row.get('open_failed', 0)),
                close_success= _safe_int(row.get('close_success', 0)),
                close_failed = _safe_int(row.get('close_failed', 0)),
                contribution = _safe_float(row.get('contribution', 0)),
                reduction    = _safe_float(row.get('reduction', 0)),
                tagging      = str(row.get('tagging', '') or ''),
            ))
        RcdBayResult.objects.bulk_create(objs)


# ── Main entry point ──────────────────────────────────────────────────────────

def run_full_calculation(session_id: int):
    """
    Entry point utama: jalankan kalkulasi RTU dan/atau RCD untuk satu session.
    Update session.status sepanjang proses.
    """
    from .models import ScadaAvSession

    session = ScadaAvSession.objects.get(pk=session_id)
    session.status = 'processing'
    session.error_message = ''
    session.save(update_fields=['status', 'error_message'])

    t0 = time.time()
    try:
        file_dict = _build_file_dict(session)
        if not file_dict:
            raise ValueError('Tidak ada file yang diupload untuk sesi ini.')

        master     = session.master
        start_date = session.periode_awal
        end_date   = session.periode_akhir

        if session.calc_type in ('rtu', 'both'):
            logger.info(f'[ScadaAV] Mulai kalkulasi RTU — session {session_id}')
            rtu_result = run_rtu(dict(file_dict), start_date, end_date, master=master)
            _save_rtu_results(session, rtu_result)
            logger.info(f'[ScadaAV] RTU selesai — {session.rtu_results.count()} RTU tersimpan')

        if session.calc_type in ('rcd', 'both'):
            # Reset BytesIO position untuk pembacaan ulang
            for f in file_dict.values():
                f.seek(0)
            logger.info(f'[ScadaAV] Mulai kalkulasi RCD — session {session_id}')
            rcd_result = run_rcd(dict(file_dict), start_date, end_date, master=master)
            _save_rcd_results(session, rcd_result)
            logger.info(f'[ScadaAV] RCD selesai')

        session.status        = 'done'
        session.durasi_hitung = round(time.time() - t0, 2)
        session.save(update_fields=['status', 'durasi_hitung'])

    except Exception as exc:
        import traceback as _tb
        tb_str = _tb.format_exc()
        logger.exception(f'[ScadaAV] Kalkulasi gagal — session {session_id}: {exc}')
        session.status        = 'error'
        session.error_message = tb_str
        session.save(update_fields=['status', 'error_message'])
        raise
