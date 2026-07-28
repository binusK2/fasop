/**
 * FASOP — Tombol "Kosongkan Data Logsheet" untuk Google Sheets.
 *
 * Pasang di spreadsheet logsheet (Extensions → Apps Script), tempel kode ini,
 * isi FASOP_DOMAIN + API_KEY di bawah, Save. Refresh spreadsheet → muncul menu
 * "FASOP" di bar atas dengan item "Kosongkan Data Logsheet".
 *
 * Cara kerja: mengambil daftar range dari endpoint /api/v1/logsheet/ranges/
 * (sinkron dengan master titik di server), lalu meng-clear ISI sel saja —
 * format, judul, border, dan formula tetap utuh. Hanya angka data yang hilang.
 *
 * Opsional: taruh tombol gambar di sheet (Insert → Drawing), lalu klik kanan
 * gambar → Assign script → ketik  kosongkanDataLogsheet
 */

var FASOP_DOMAIN = '__FASOP_DOMAIN__';   // mis. fasop.domain (tanpa https://)
var API_KEY      = '__API_KEY__';        // sama dengan API_KEY di .env FASOP

function onOpen() {
  SpreadsheetApp.getUi()
    .createMenu('FASOP')
    .addItem('Kosongkan Data Logsheet', 'kosongkanDataLogsheet')
    .addToUi();
}

function kosongkanDataLogsheet() {
  var ui = SpreadsheetApp.getUi();
  var jawab = ui.alert(
    'Kosongkan Data Logsheet',
    'Semua nilai data (48 kolom waktu) akan dikosongkan. Format & judul tetap. Lanjut?',
    ui.ButtonSet.YES_NO);
  if (jawab != ui.Button.YES) return;

  var resp = UrlFetchApp.fetch('https://' + FASOP_DOMAIN + '/api/v1/logsheet/ranges/', {
    method: 'get',
    headers: { 'X-API-Key': API_KEY },
    muteHttpExceptions: true
  });
  if (resp.getResponseCode() != 200) {
    ui.alert('Gagal ambil daftar range dari FASOP (HTTP ' + resp.getResponseCode() + ').');
    return;
  }
  var ranges = JSON.parse(resp.getContentText()).ranges || [];
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var ok = 0, gagal = 0;
  ranges.forEach(function (a1) {
    try { ss.getRange(a1).clearContent(); ok++; }
    catch (e) { gagal++; }   // sheet/nama tak cocok → lewati
  });
  ui.alert('Selesai. ' + ok + ' blok dikosongkan' +
           (gagal ? ', ' + gagal + ' dilewati (nama sheet beda).' : '.'));
}
