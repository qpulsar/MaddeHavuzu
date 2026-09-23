/* Optik Okuma — sihirbaz sayfaları için ortak yardımcılar. */
(function (window, document) {
    'use strict';

    /** CSRF belirteci: base.html <body hx-headers> içinden, yoksa çerezden. */
    function csrfToken() {
        try {
            var h = JSON.parse(document.body.getAttribute('hx-headers') || '{}');
            if (h['X-CSRFToken']) return h['X-CSRFToken'];
        } catch (e) { /* yok say */ }
        var input = document.querySelector('input[name="csrfmiddlewaretoken"]');
        if (input) return input.value;
        var m = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
        return m ? decodeURIComponent(m[1]) : '';
    }


    function formatKB(size) { return (size / 1024).toFixed(1) + ' KB'; }

    /**
     * Sürükle-bırak dosya alanı.
     * opts: {zone, input, list, submit, countEl}
     */
    function initDropzone(opts) {
        var zone = document.getElementById(opts.zone);
        var input = document.getElementById(opts.input);
        var list = document.getElementById(opts.list);
        var submit = document.getElementById(opts.submit);
        var countEl = opts.countEl ? document.getElementById(opts.countEl) : null;
        if (!zone || !input) return;

        function render() {
            var files = input.files;
            list.innerHTML = '';
            for (var i = 0; i < files.length; i++) {
                var li = document.createElement('li');
                li.className = 'list-group-item d-flex justify-content-between align-items-center';
                var name = document.createElement('span');
                name.textContent = (i + 1) + '. ' + files[i].name;
                var size = document.createElement('span');
                size.className = 'text-muted small';
                size.textContent = formatKB(files[i].size);
                li.appendChild(name);
                li.appendChild(size);
                list.appendChild(li);
            }
            list.classList.toggle('d-none', files.length === 0);
            if (submit) submit.disabled = files.length === 0;
            if (countEl) countEl.textContent = files.length;
        }

        zone.addEventListener('click', function (e) {
            if (e.target !== input) input.click();
        });
        zone.addEventListener('keydown', function (e) {
            if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); input.click(); }
        });
        zone.addEventListener('dragover', function (e) {
            e.preventDefault();
            zone.classList.add('is-dragover');
        });
        zone.addEventListener('dragleave', function () { zone.classList.remove('is-dragover'); });
        zone.addEventListener('drop', function (e) {
            e.preventDefault();
            zone.classList.remove('is-dragover');
            input.files = e.dataTransfer.files;
            render();
        });
        input.addEventListener('change', render);

        var form = input.form;
        if (form && submit) {
            form.addEventListener('submit', function () {
                submit.disabled = true;
                submit.innerHTML = '<span class="spinner-border spinner-border-sm me-2" role="status"></span>Yükleniyor...';
                var progress = form.querySelector('.js-upload-progress');
                if (progress) progress.classList.remove('d-none');
            });
        }
        render();
    }

    window.OptikWizard = {csrfToken: csrfToken, initDropzone: initDropzone, formatKB: formatKB};
})(window, document);
