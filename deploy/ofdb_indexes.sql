-- ============================================================================
-- Index yang disarankan di OFDB (dbup2bmakasar @ 192.168.19.1) untuk fitur
-- Kinerja SCADATEL di FASOP (app up2bmakassar).
--
-- FASOP hanya MEMBACA OFDB (user fasop_readonly). Script ini BUKAN dijalankan
-- oleh FASOP -- serahkan ke DBA/admin OFDB, jalankan sekali di luar jam sibuk.
-- Tanpa index ini query tetap benar, cuma lambat (scan tabel histori yang
-- ratusan juta baris) sehingga sinkronisasi harian bisa timeout.
--
-- Cek dulu apakah index-nya sudah ada:
--   EXEC sp_helpindex 'scd_his_analog';
--   EXEC sp_helpindex 'scd_his_digital';
--   EXEC sp_helpindex 'scd_his_message';
--   EXEC sp_helpindex 'scd_c_point';
--
-- ONLINE=ON hanya jalan di SQL Server Enterprise. Di Standard, hapus opsi itu
-- (tabelnya akan terkunci selama index dibuat).
-- ============================================================================

-- ── Histori transisi analog/digital ─────────────────────────────────────────
-- Dipakai sync_kinerja_analog / sync_kinerja_digital:
--   WHERE kesimpulan='VALID' AND datum_1 < @akhir AND datum_2 > @awal GROUP BY point_number
-- datum_1 jadi kolom pertama karena itu yang di-range-scan; kolom lain di-INCLUDE
-- supaya query cukup baca index-nya saja (covering index).

CREATE NONCLUSTERED INDEX IX_scd_his_analog_datum1
    ON dbo.scd_his_analog (datum_1)
    INCLUDE (datum_2, point_number, kesimpulan)
    WITH (ONLINE = ON, FILLFACTOR = 90);

CREATE NONCLUSTERED INDEX IX_scd_his_digital_datum1
    ON dbo.scd_his_digital (datum_1)
    INCLUDE (datum_2, point_number, kesimpulan)
    WITH (ONLINE = ON, FILLFACTOR = 90);

-- Untuk penelusuran per titik (histori satu point, dan fallback status terakhir
-- sebelum tanggal tertentu).

CREATE NONCLUSTERED INDEX IX_scd_his_analog_point_datum1
    ON dbo.scd_his_analog (point_number, datum_1)
    INCLUDE (datum_2, kesimpulan)
    WITH (ONLINE = ON, FILLFACTOR = 90);

CREATE NONCLUSTERED INDEX IX_scd_his_digital_point_datum1
    ON dbo.scd_his_digital (point_number, datum_1)
    INCLUDE (datum_2, kesimpulan)
    WITH (ONLINE = ON, FILLFACTOR = 90);

-- ── SOE log ─────────────────────────────────────────────────────────────────
-- Halaman SOE Log query on-demand: WHERE time_stamp BETWEEN ... ORDER BY time_stamp DESC
-- (+ LIKE pada path1text..path4text). resolve_rc_result juga menembak tabel ini
-- lewat kombinasi path1..path5 + time_stamp.

CREATE NONCLUSTERED INDEX IX_scd_his_message_timestamp
    ON dbo.scd_his_message (time_stamp)
    INCLUDE (path1, path2, path3, path4, path5,
             path1text, path2text, path3text, path4text, path5text,
             msgstatus, value, tag, msgoperator, priority)
    WITH (ONLINE = ON, FILLFACTOR = 90);

CREATE NONCLUSTERED INDEX IX_scd_his_message_path_timestamp
    ON dbo.scd_his_message (path1, path2, path3, path4, path5, time_stamp)
    INCLUDE (tag, msec)
    WITH (ONLINE = ON, FILLFACTOR = 90);

-- ── RC ──────────────────────────────────────────────────────────────────────
-- sync_rc: WHERE datum_1 BETWEEN ... ORDER BY datum_1

CREATE NONCLUSTERED INDEX IX_scd_his_rc_datum1
    ON dbo.scd_his_rc (datum_1)
    WITH (ONLINE = ON, FILLFACTOR = 90);

-- ── Master titik ────────────────────────────────────────────────────────────
-- get_kinerja_points: WHERE kinerja=1 AND id_pointtype>0 AND point_type=?
-- Tabelnya kecil, jadi ini opsional -- berguna kalau scd_c_point sudah puluhan
-- ribu baris.

CREATE NONCLUSTERED INDEX IX_scd_c_point_kinerja
    ON dbo.scd_c_point (kinerja, point_type, id_pointtype)
    INCLUDE (point_number, path1, path2, path3, path4, path5,
             path1text, path2text, path3text, path4text)
    WITH (ONLINE = ON, FILLFACTOR = 90);
