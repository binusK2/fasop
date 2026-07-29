/**
 * FASOP — Clear Data Logsheet untuk Google Sheets.
 *
 * DUA MODE:
 *   1) Tombol MANUAL  — menu "FASOP → Kosongkan Data Logsheet" (ada konfirmasi).
 *   2) AUTO harian    — hapus otomatis tiap dini hari (~00:15) via time-trigger.
 *
 * Pasang: Extensions → Apps Script → tempel kode ini → isi FASOP_DOMAIN + API_KEY
 * → Save → refresh spreadsheet. Menu "FASOP" muncul di bar atas.
 *
 * Mengaktifkan AUTO-CLEAR harian:
 *   Menu FASOP → "Pasang Auto-Clear Harian (~00:15)"  (cukup sekali klik).
 *   Untuk mematikan: menu FASOP → "Hapus Auto-Clear Harian".
 *
 * Cara kerja clear: ambil daftar range dari /api/v1/logsheet/ranges/ (sinkron
 * dgn master titik server), lalu hapus ISI sel data saja — format, judul, border,
 * formula tetap utuh. Hanya angka data yang hilang.
 *
 * Kenapa ~00:15 aman: arsip .xlsx kemarin sudah tersimpan (command FASOP 00:05),
 * dan data hari baru baru masuk ~00:31 (slot 00:30). Trigger Apps Script punya
 * jitter ±15 mnt (00:00–00:30), tetap di celah aman sebelum data baru masuk.
 */

var FASOP_DOMAIN = '__FASOP_DOMAIN__';   // mis. fasop.domain (tanpa https://)
var API_KEY      = '__API_KEY__';        // sama dengan API_KEY di .env FASOP

var TRIGGER_FN   = 'clearOtomatisHarian';  // jangan diubah


function onOpen() {
  SpreadsheetApp.getUi()
    .createMenu('FASOP')
    .addItem('Kosongkan Data Logsheet (manual)', 'kosongkanDataLogsheet')
    .addSeparator()
    .addItem('Pasang Auto-Clear Harian (~00:15)', 'pasangTriggerHarian')
    .addItem('Hapus Auto-Clear Harian', 'hapusTriggerHarian')
    .addToUi();
}


/** Inti: ambil range dari FASOP lalu clear isinya. Kembalikan {ok, gagal}. */
function _clearRangesLogsheet() {
  var resp = UrlFetchApp.fetch('https://' + FASOP_DOMAIN + '/api/v1/logsheet/ranges/', {
    method: 'get',
    headers: { 'X-API-Key': API_KEY },
    muteHttpExceptions: true
  });
  if (resp.getResponseCode() != 200) {
    throw new Error('Gagal ambil daftar range dari FASOP (HTTP ' + resp.getResponseCode() + ').');
  }
  var ranges = JSON.parse(resp.getContentText()).ranges || [];
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var ok = 0, gagal = 0;
  ranges.forEach(function (a1) {
    try { ss.getRange(a1).clearContent(); ok++; }
    catch (e) { gagal++; }   // sheet/nama tak cocok → lewati
  });
  return { ok: ok, gagal: gagal };
}


/** MODE 1 — tombol manual, dengan konfirmasi & pesan hasil. */
function kosongkanDataLogsheet() {
  var ui = SpreadsheetApp.getUi();
  var jawab = ui.alert(
    'Kosongkan Data Logsheet',
    'Semua nilai data (48 kolom waktu) akan dikosongkan. Format & judul tetap. Lanjut?',
    ui.ButtonSet.YES_NO);
  if (jawab != ui.Button.YES) return;
  try {
    var r = _clearRangesLogsheet();
    ui.alert('Selesai. ' + r.ok + ' blok dikosongkan' +
             (r.gagal ? ', ' + r.gagal + ' dilewati (nama sheet beda).' : '.'));
  } catch (e) {
    ui.alert('Gagal: ' + e.message);
  }
}


/** MODE 2 — dijalankan oleh time-trigger harian. TANPA UI (headless). */
function clearOtomatisHarian() {
  try {
    var r = _clearRangesLogsheet();
    Logger.log('Auto-clear OK: %s blok dikosongkan, %s dilewati.', r.ok, r.gagal);
  } catch (e) {
    Logger.log('Auto-clear GAGAL: %s', e.message);
  }
}


/** Pasang trigger harian ~00:15. Hapus dulu yg lama agar tak dobel. */
function pasangTriggerHarian() {
  hapusTriggerHarian(true);
  ScriptApp.newTrigger(TRIGGER_FN)
    .timeBased()
    .atHour(0)
    .nearMinute(15)   // Apps Script: berjalan sekitar 00:00–00:30
    .everyDays(1)
    .create();
  SpreadsheetApp.getUi().alert(
    'Auto-Clear harian AKTIF.\n\nSpreadsheet akan dikosongkan otomatis tiap dini ' +
    'hari sekitar pukul 00:15 (jitter Apps Script ±15 mnt). Arsip .xlsx kemarin ' +
    'sudah aman tersimpan sebelum ini berjalan.');
}


/** Hapus semua trigger untuk fungsi auto-clear. */
function hapusTriggerHarian(diam) {
  var n = 0;
  ScriptApp.getProjectTriggers().forEach(function (t) {
    if (t.getHandlerFunction() === TRIGGER_FN) { ScriptApp.deleteTrigger(t); n++; }
  });
  if (!diam) {
    SpreadsheetApp.getUi().alert(n ? ('Auto-Clear harian dimatikan (' + n + ' trigger dihapus).')
                                   : 'Tidak ada trigger auto-clear yang terpasang.');
  }
}
