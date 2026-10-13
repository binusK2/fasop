/*
 * Landing page FASOP (devices/templates/devices/landing.html).
 *
 * Dimuat di <head> TANPA defer: baris pertama menandai <html class="js"> sebelum
 * halaman tergambar, supaya animasi muncul-saat-digulir hanya menyembunyikan
 * konten kalau skrip ini benar-benar jalan. Kalau berkas ini gagal dimuat,
 * seluruh isi halaman tetap terlihat — hanya animasinya yang hilang.
 *
 * Berkas statis, bukan <script> inline: halaman ini sengaja jadi halaman
 * pertama FASOP yang lolos CSP tanpa 'unsafe-inline' (lihat CLAUDE.md).
 */
document.documentElement.classList.add('js');

document.addEventListener('DOMContentLoaded', function () {
  'use strict';

  var hemat = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  /* ── Ilustrasi jaringan: simpul & saluran ABSTRAK, bukan peta GI sungguhan ── */
  var N = {
    a: [110, 110], b: [250, 66], c: [432, 92], d: [544, 198], e: [522, 364], f: [392, 456],
    g: [210, 446], h: [76, 330], i: [160, 222], j: [438, 256], k: [336, 150], l: [244, 348]
  };
  var E = [['a', 'b'], ['b', 'k'], ['k', 'c'], ['c', 'd'], ['d', 'j'], ['j', 'e'], ['e', 'f'], ['f', 'l'],
           ['l', 'g'], ['g', 'h'], ['h', 'i'], ['i', 'a'], ['b', 'i'], ['c', 'j'], ['f', 'j'], ['g', 'l']];
  var JARI = ['i', 'k', 'j', 'l'];
  var PUSAT = [300, 262];
  var NS = 'http://www.w3.org/2000/svg';

  function el(tag, attrs, induk) {
    var x = document.createElementNS(NS, tag);
    for (var k in attrs) { x.setAttribute(k, attrs[k]); }
    if (induk) { induk.appendChild(x); }
    return x;
  }
  function lengkung(p, q, tekuk) {
    var mx = (p[0] + q[0]) / 2, my = (p[1] + q[1]) / 2, dx = q[0] - p[0], dy = q[1] - p[1];
    return 'M' + p[0] + ',' + p[1] + ' Q' + (mx - dy * tekuk) + ',' + (my + dx * tekuk) + ' ' + q[0] + ',' + q[1];
  }

  var gE = document.getElementById('edges'), gF = document.getElementById('flows'),
      gP = document.getElementById('pulses'), gN = document.getElementById('nodes');
  if (gE && gF && gP && gN) {
    var jalur = [];
    E.forEach(function (e, idx) { jalur.push(lengkung(N[e[0]], N[e[1]], idx % 2 ? 0.12 : -0.1)); });
    JARI.forEach(function (s) { jalur.push(lengkung(N[s], PUSAT, 0.06)); });
    jalur.forEach(function (d, idx) {
      el('path', { d: d, 'class': 'edge' }, gE);
      if (idx % 2 === 0 || idx >= E.length) {
        var f = el('path', { d: d, 'class': 'flow' + (idx % 3 === 0 ? ' slow' : '') }, gF);
        f.style.animationDelay = (-(idx * 0.37)) + 's';
      }
      // Titik energi yang berjalan di saluran memakai SMIL, yang tidak ikut
      // dimatikan oleh CSS prefers-reduced-motion — jadi dilewati di sini.
      if (!hemat && (idx % 3 === 1 || idx >= E.length)) {
        var id = 'p' + idx;
        el('path', { d: d, id: id, fill: 'none' }, gP);
        var c = el('circle', { r: 3.2, 'class': 'pulse' }, gP);
        var am = el('animateMotion', {
          dur: (2.4 + (idx % 4) * 0.7) + 's', repeatCount: 'indefinite', begin: (-(idx * 0.53)) + 's',
          keyPoints: idx % 2 ? '0;1' : '1;0', keyTimes: '0;1', calcMode: 'linear'
        }, c);
        el('mpath', { href: '#' + id }, am);
      }
    });
    Object.keys(N).forEach(function (k, idx) {
      var p = N[k];
      var halo = el('circle', { cx: p[0], cy: p[1], r: 9, 'class': 'halo' }, gN);
      halo.style.animationDelay = (-(idx * 0.45)) + 's';
      el('circle', { cx: p[0], cy: p[1], r: 9, 'class': 'node' }, gN);
      el('circle', { cx: p[0], cy: p[1], r: 3.2, 'class': 'node-core' }, gN);
    });
  }

  /* ── Sapaan & jam WITA (UTC+8, tanpa musim panas) ── */
  var HARI = ['Minggu', 'Senin', 'Selasa', 'Rabu', 'Kamis', 'Jumat', 'Sabtu'];
  var BULAN = ['Januari', 'Februari', 'Maret', 'April', 'Mei', 'Juni', 'Juli', 'Agustus',
               'September', 'Oktober', 'November', 'Desember'];
  var sapa = document.getElementById('greet'), kapan = document.getElementById('when');
  function dua(n) { return (n < 10 ? '0' : '') + n; }
  function detak() {
    var kini = new Date();
    var t = new Date(kini.getTime() + (kini.getTimezoneOffset() + 480) * 60000);
    var j = t.getHours();
    sapa.textContent = j >= 4 && j < 11 ? 'Selamat pagi'
                     : j >= 11 && j < 15 ? 'Selamat siang'
                     : j >= 15 && j < 18 ? 'Selamat sore' : 'Selamat malam';
    kapan.textContent = HARI[t.getDay()] + ', ' + t.getDate() + ' ' + BULAN[t.getMonth()] + ' ' + t.getFullYear() + ' · ';
    var b = document.createElement('b');
    b.textContent = dua(j) + ':' + dua(t.getMinutes()) + ':' + dua(t.getSeconds());
    kapan.appendChild(b);
    kapan.appendChild(document.createTextNode(' WITA'));
  }
  if (sapa && kapan) { detak(); setInterval(detak, 1000); }

  /* ── Navigasi berlatar saat digulir ── */
  var nav = document.getElementById('nav');
  function gulir() { nav.classList.toggle('scrolled', window.scrollY > 8); }
  if (nav) { gulir(); window.addEventListener('scroll', gulir, { passive: true }); }

  /* ── Muncul saat digulir ── */
  var muncul = document.querySelectorAll('.reveal');
  if ('IntersectionObserver' in window && !hemat) {
    var io = new IntersectionObserver(function (entri) {
      entri.forEach(function (en) {
        if (en.isIntersecting) { en.target.classList.add('in'); io.unobserve(en.target); }
      });
    }, { threshold: 0.12, rootMargin: '0px 0px -40px 0px' });
    muncul.forEach(function (x) { io.observe(x); });
  } else {
    muncul.forEach(function (x) { x.classList.add('in'); });
  }

  /* ── Sorotan kartu modul mengikuti kursor ── */
  document.querySelectorAll('.mod').forEach(function (kartu) {
    kartu.addEventListener('pointermove', function (ev) {
      var r = kartu.getBoundingClientRect();
      kartu.style.setProperty('--mx', (ev.clientX - r.left) + 'px');
      kartu.style.setProperty('--my', (ev.clientY - r.top) + 'px');
    });
  });

  /* ── Pengumuman bisa ditutup (hanya di layar ini; muncul lagi saat dimuat ulang) ── */
  var notice = document.getElementById('notice'), tutup = document.getElementById('notice-x');
  if (notice && tutup) {
    tutup.addEventListener('click', function () {
      notice.classList.add('hide');
      setTimeout(function () { notice.hidden = true; }, 350);
    });
  }
});
