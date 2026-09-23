/* Optik Okuma — kayıt listesi, kayıt düzenleme ve puanlama sayfaları. */
(function () {
    'use strict';

    function csrfToken() {
        var el = document.querySelector('input[name=csrfmiddlewaretoken]');
        return el ? el.value : '';
    }

    function postJSON(url, body) {
        return fetch(url, {
            method: 'POST',
            credentials: 'same-origin',
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'application/json',
                'X-Requested-With': 'XMLHttpRequest',
                'X-CSRFToken': csrfToken()
            },
            body: JSON.stringify(body || {})
        }).then(function (r) { return r.json(); });
    }

    // data-confirm taşıyan formlar gönderilmeden önce onay ister
    document.addEventListener('submit', function (e) {
        var msg = e.target.getAttribute && e.target.getAttribute('data-confirm');
        if (msg && !window.confirm(msg)) e.preventDefault();
    });

    // ── Kayıt listesi: seçim + silme ────────────────────────────────────
    function initRecordList() {
        var root = document.getElementById('optikRecordList');
        if (!root) return;
        var deleteUrl = root.dataset.deleteUrl;
        var deleteSelectedUrl = root.dataset.deleteSelectedUrl;
        var selectAll = document.getElementById('selectAll');
        var btn = document.getElementById('deleteSelectedBtn');
        var countEl = document.getElementById('selectedCount');

        function checks() { return root.querySelectorAll('.row-check'); }
        function checked() { return root.querySelectorAll('.row-check:checked'); }
        function update() {
            var c = checked().length, a = checks().length;
            countEl.textContent = c;
            btn.disabled = c === 0;
            selectAll.checked = a > 0 && c === a;
        }
        function handle(d) {
            if (d.success) window.location.reload();
            else window.alert('Hata: ' + (d.error || 'Silinemedi'));
        }

        selectAll.addEventListener('change', function () {
            checks().forEach(function (cb) { cb.checked = selectAll.checked; });
            update();
        });
        root.addEventListener('change', function (e) {
            if (e.target.classList.contains('row-check')) update();
        });
        root.addEventListener('click', function (e) {
            var del = e.target.closest('[data-delete-record]');
            if (!del) return;
            if (!window.confirm('Bu kaydı silmek istediğinize emin misiniz?')) return;
            postJSON(deleteUrl.replace('__RID__', encodeURIComponent(del.dataset.deleteRecord)))
                .then(handle).catch(function () { window.alert('Sunucu hatası'); });
        });
        btn.addEventListener('click', function () {
            var c = checked();
            if (c.length === 0) return;
            if (!window.confirm(c.length + ' kayıt silinecek. Devam?')) return;
            var ids = Array.prototype.map.call(c, function (cb) { return cb.value; });
            postJSON(deleteSelectedUrl, { record_ids: ids })
                .then(handle).catch(function () { window.alert('Sunucu hatası'); });
        });
        update();
    }

    // ── Tam ekran görüntü + tıkla-yakınlaş ──────────────────────────────
    function initZoom() {
        var modal = document.getElementById('optikZoomModal');
        if (!modal) return;
        var img = document.getElementById('optikZoomImg');
        var title = document.getElementById('optikZoomTitle');
        var level = 1;

        function reset() {
            level = 1;
            img.style.transform = 'scale(1)';
            img.style.maxWidth = '100%';
            modal.classList.remove('zoomed');
        }
        function open(src, text) {
            if (src) img.src = src;
            title.textContent = text || '';
            reset();
            modal.classList.add('open');
            document.body.style.overflow = 'hidden';
        }
        function close() {
            modal.classList.remove('open', 'zoomed');
            document.body.style.overflow = '';
        }

        document.addEventListener('click', function (e) {
            var t = e.target.closest('[data-zoom-src]');
            if (t) { open(t.dataset.zoomSrc, t.dataset.zoomTitle); return; }
            var z = e.target.closest('.optik-zoomable');
            if (z) { open(z.currentSrc || z.src, z.dataset.zoomTitle); return; }
            if (e.target.closest('[data-zoom-open]')) {
                var s = document.querySelector('.optik-sidebar-image');
                if (s) open(s.currentSrc || s.src, s.dataset.zoomTitle);
            }
        });
        modal.addEventListener('click', function (e) {
            if (e.target === img) return;
            close();
        });
        modal.addEventListener('dblclick', close);
        img.addEventListener('click', function (e) {
            e.stopPropagation();
            level = level === 1 ? 2 : (level === 2 ? 3 : 1);
            if (level === 1) { reset(); return; }
            var rect = img.getBoundingClientRect();
            var px = (e.clientX - rect.left) / rect.width;
            var py = (e.clientY - rect.top) / rect.height;
            img.style.maxWidth = 'none';
            img.style.transform = 'scale(' + level + ')';
            var nr = img.getBoundingClientRect();
            modal.scrollLeft = nr.width * px - modal.clientWidth / 2;
            modal.scrollTop = nr.height * py - modal.clientHeight / 2;
            modal.classList.add('zoomed');
        });
        document.addEventListener('keydown', function (e) {
            if (e.key === 'Escape') close();
        });
    }

    // ── Kayıt düzenleme: cevap butonları + değişiklik sayacı ────────────
    function initRecordEdit() {
        var form = document.getElementById('editForm');
        if (!form) return;

        function updateStats() {
            var changed = 0;
            form.querySelectorAll('.answer-row').forEach(function (row) {
                var hidden = row.querySelector('input[type="hidden"]');
                var raw = row.querySelector('.optik-raw-tag');
                if (raw && hidden) {
                    if (raw.textContent.trim() !== (hidden.value || '-')) changed++;
                }
            });
            var el = document.getElementById('changeCount');
            el.textContent = changed > 0 ? changed + ' değişiklik' : '';
        }

        form.addEventListener('click', function (e) {
            var b = e.target.closest('.optik-opt-btn');
            if (!b) return;
            var q = b.dataset.q;
            form.querySelectorAll('.optik-opt-btn[data-q="' + q + '"]').forEach(function (x) {
                x.classList.remove('selected');
            });
            b.classList.add('selected');
            form.querySelector('input[name="ans_' + q + '"]').value = b.dataset.val;
            updateStats();
        });

        var toggle = document.querySelector('[data-sidebar-toggle]');
        if (toggle) {
            toggle.addEventListener('click', function () {
                document.getElementById('imageSidebar').classList.toggle('collapsed');
            });
        }
        updateStats();
    }

    document.addEventListener('DOMContentLoaded', function () {
        initRecordList();
        initZoom();
        initRecordEdit();
    });
})();
