/*
 * Popup konfirmasi & info bersama -- pengganti confirm()/alert() bawaan
 * browser di seluruh FASOP. Dimuat sekali dari base.html/opsis_base.html
 * (setelah bootstrap.bundle.js), dipakai lewat empat fungsi global:
 *
 *   fasopConfirm(pesan, onYa, opsi)   -- popup Ya/Batal, jalankan onYa() saat "Ya"
 *   fasopAlert(pesan, opsi)           -- popup info satu tombol "OK"
 *   fasopPrompt(pesan, onIsi, opsi)   -- pengganti prompt(): popup isian teks,
 *                                        jalankan onIsi(nilai) saat "OK" (opsi.default = nilai awal)
 *   confirmSubmit(formEl, pesan, opsi)-- untuk <form onsubmit="return confirmSubmit(this, '...')">
 *   confirmNav(linkEl, pesan, opsi)   -- untuk <a onclick="return confirmNav(this, '...')" href="...">
 *
 * confirmSubmit/confirmNav SELALU mengembalikan false (menahan submit/navigasi
 * bawaan yang synchronous), lalu melanjutkan submit/navigasi sendiri lewat
 * JS setelah tombol "Ya" ditekan -- popup custom sifatnya asinkron (menunggu
 * klik), tidak bisa meniru nilai balik confirm()/prompt() yang langsung tersedia.
 *
 * opsi: {title, danger (default true), okLabel (default 'Ya')}
 */
(function (global) {
    var MODAL_HTML =
        '<div class="modal fade" id="fasopConfirmModal" tabindex="-1" aria-hidden="true">' +
        '  <div class="modal-dialog modal-dialog-centered" style="max-width:380px;">' +
        '    <div class="modal-content" style="border-radius:14px;border:none;">' +
        '      <div class="modal-body p-4 text-center">' +
        '        <div id="fasopConfirmIconWrap" style="width:52px;height:52px;border-radius:50%;display:flex;align-items:center;justify-content:center;margin:0 auto 14px;">' +
        '          <i id="fasopConfirmIcon" style="font-size:22px;"></i>' +
        '        </div>' +
        '        <h6 id="fasopConfirmTitle" style="font-size:16px;font-weight:700;margin-bottom:6px;"></h6>' +
        '        <p id="fasopConfirmDesc" style="font-size:13px;color:#64748b;white-space:pre-line;"></p>' +
        '        <div class="d-flex gap-2 justify-content-center mt-3">' +
        '          <button type="button" class="btn btn-outline-secondary" data-bs-dismiss="modal">Batal</button>' +
        '          <button type="button" id="fasopConfirmOk" class="btn px-4"></button>' +
        '        </div>' +
        '      </div>' +
        '    </div>' +
        '  </div>' +
        '</div>' +
        '<div class="modal fade" id="fasopAlertModal" tabindex="-1" aria-hidden="true">' +
        '  <div class="modal-dialog modal-dialog-centered" style="max-width:380px;">' +
        '    <div class="modal-content" style="border-radius:14px;border:none;">' +
        '      <div class="modal-body p-4 text-center">' +
        '        <div style="width:52px;height:52px;background:#eff6ff;border-radius:50%;display:flex;align-items:center;justify-content:center;margin:0 auto 14px;">' +
        '          <i class="bi bi-info-circle" style="font-size:22px;color:#3b82f6;"></i>' +
        '        </div>' +
        '        <p id="fasopAlertDesc" style="font-size:13.5px;color:#334155;margin-bottom:0;white-space:pre-line;"></p>' +
        '        <div class="mt-3">' +
        '          <button type="button" class="btn btn-primary px-4" data-bs-dismiss="modal">OK</button>' +
        '        </div>' +
        '      </div>' +
        '    </div>' +
        '  </div>' +
        '</div>' +
        '<div class="modal fade" id="fasopPromptModal" tabindex="-1" aria-hidden="true">' +
        '  <div class="modal-dialog modal-dialog-centered" style="max-width:380px;">' +
        '    <div class="modal-content" style="border-radius:14px;border:none;">' +
        '      <form id="fasopPromptForm" class="modal-body p-4">' +
        '        <p id="fasopPromptDesc" style="font-size:13.5px;color:#334155;"></p>' +
        '        <input type="text" id="fasopPromptInput" class="form-control form-control-sm mb-1">' +
        '        <div class="d-flex gap-2 justify-content-center mt-3">' +
        '          <button type="button" class="btn btn-outline-secondary" data-bs-dismiss="modal">Batal</button>' +
        '          <button type="submit" class="btn btn-primary px-4">OK</button>' +
        '        </div>' +
        '      </form>' +
        '    </div>' +
        '  </div>' +
        '</div>';

    function ensureModals() {
        if (document.getElementById('fasopConfirmModal')) return;
        var wrap = document.createElement('div');
        wrap.innerHTML = MODAL_HTML;
        document.body.appendChild(wrap);
    }

    function fasopConfirm(message, onYa, opsi) {
        opsi = opsi || {};
        ensureModals();

        document.getElementById('fasopConfirmTitle').textContent = opsi.title || 'Konfirmasi';
        document.getElementById('fasopConfirmDesc').textContent = message;

        var danger = opsi.danger !== false;
        var iconWrap = document.getElementById('fasopConfirmIconWrap');
        var icon = document.getElementById('fasopConfirmIcon');
        var okBtn = document.getElementById('fasopConfirmOk');
        iconWrap.style.background = danger ? '#fef2f2' : '#eff6ff';
        icon.className = danger ? 'bi bi-exclamation-triangle' : 'bi bi-question-circle';
        icon.style.color = danger ? '#ef4444' : '#3b82f6';
        okBtn.className = 'btn px-4 ' + (danger ? 'btn-danger' : 'btn-primary');
        okBtn.textContent = opsi.okLabel || 'Ya';

        var modalEl = document.getElementById('fasopConfirmModal');
        var modal = bootstrap.Modal.getOrCreateInstance(modalEl);

        var handler = function () {
            okBtn.removeEventListener('click', handler);
            modal.hide();
            onYa();
        };
        okBtn.addEventListener('click', handler);
        modal.show();
    }

    function fasopAlert(message, opsi) {
        opsi = opsi || {};
        ensureModals();
        document.getElementById('fasopAlertDesc').textContent = message;
        bootstrap.Modal.getOrCreateInstance(document.getElementById('fasopAlertModal')).show();
    }

    function fasopPrompt(message, onIsi, opsi) {
        opsi = opsi || {};
        ensureModals();

        document.getElementById('fasopPromptDesc').textContent = message;
        var input = document.getElementById('fasopPromptInput');
        input.value = opsi.default || '';

        var modalEl = document.getElementById('fasopPromptModal');
        var modal = bootstrap.Modal.getOrCreateInstance(modalEl);
        var form = document.getElementById('fasopPromptForm');

        var handler = function (e) {
            e.preventDefault();
            form.removeEventListener('submit', handler);
            modal.hide();
            onIsi(input.value);
        };
        form.addEventListener('submit', handler);
        modal.show();
        modalEl.addEventListener('shown.bs.modal', function () { input.focus(); }, { once: true });
    }

    function confirmSubmit(formEl, message, opsi) {
        fasopConfirm(message, function () { formEl.submit(); }, opsi);
        return false;
    }

    function confirmNav(linkEl, message, opsi) {
        var href = linkEl.getAttribute('href');
        fasopConfirm(message, function () { window.location.href = href; }, opsi);
        return false;
    }

    global.fasopConfirm = fasopConfirm;
    global.fasopAlert = fasopAlert;
    global.fasopPrompt = fasopPrompt;
    global.confirmSubmit = confirmSubmit;
    global.confirmNav = confirmNav;
})(window);
