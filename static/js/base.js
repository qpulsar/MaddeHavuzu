    // ── Sidebar mobile close ───────────────────────────────────────────
    document.addEventListener('click', function(e) {
        const sidebar  = document.getElementById('sidebar');
        const toggler  = document.querySelector('.sidebar-toggler');
        if (window.innerWidth <= 768 && sidebar &&
            !sidebar.contains(e.target) &&
            toggler && !toggler.contains(e.target)) {
            sidebar.classList.remove('show');
        }
    });

    // ── Tema toggle ────────────────────────────────────────────────────
    (function() {
        const btn  = document.getElementById('themeToggleBtn');
        const icon = document.getElementById('themeIcon');
        const html = document.documentElement;

        function getEffectiveTheme(stored) {
            if (stored === 'system') {
                return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
            }
            return stored || 'light';
        }

        function applyThemeIcon(theme) {
            if (!icon) return;
            if (theme === 'dark') {
                icon.className = 'bi bi-moon-fill';
            } else if (theme === 'system') {
                icon.className = 'bi bi-circle-half';
            } else {
                icon.className = 'bi bi-sun-fill';
            }
        }

        // İlk yükleme — sunucu tarafından zaten set edildi, sadece icon'u güncelle
        applyThemeIcon(html.getAttribute('data-theme'));

        if (btn) {
            btn.addEventListener('click', function() {
                const current = html.getAttribute('data-theme') || 'light';
                const next = current === 'light' ? 'dark' : 'light';
                html.setAttribute('data-theme', next);
                applyThemeIcon(next);

                // Sunucuya kaydet
                const url = btn.getAttribute('data-url');
                const csrf = btn.getAttribute('data-csrf');
                if (url && csrf) {
                    fetch(url, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'X-CSRFToken': csrf
                        },
                        body: JSON.stringify({ theme: next })
                    });
                }
            });
        }

        // Sistem teması için OS değişikliklerini dinle
        window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', function(e) {
            if (html.getAttribute('data-theme') === 'system') {
                applyThemeIcon('system');
            }
        });
    })();

    // ── PDF Yükleme Animasyonu ──────────────────────────────────────────
    document.addEventListener('click', function(e) {
        const link = e.target.closest('.pdf-download-link');
        if (link) {
            const overlay = document.getElementById('pdfLoadingOverlay');
            if (overlay) {
                overlay.style.display = 'flex';
                // Trigger reflow for transition
                overlay.offsetHeight; 
                overlay.classList.add('show');
                
                // 15 saniye sonra otomatik kapat
                setTimeout(() => {
                    overlay.classList.remove('show');
                    setTimeout(() => { overlay.style.display = 'none'; }, 300);
                }, 15000);
            }
        }
    });

    // ── Global HTMX & AI Loading Kilit & Spinner ─────────────────────────────
    document.addEventListener('htmx:configRequest', function(evt) {
        const elt = evt.detail.elt;
        if (elt && (elt.tagName === 'BUTTON' || elt.tagName === 'A')) {
            elt.classList.add('disabled');
            if (elt.tagName === 'BUTTON') elt.disabled = true;
            
            // Eğer buton veya link içinde spinner yoksa spinner ekle
            if (!elt.querySelector('.spinner-border')) {
                const spinner = document.createElement('span');
                spinner.className = 'spinner-border spinner-border-sm me-1 btn-htmx-spinner';
                spinner.setAttribute('role', 'status');
                spinner.setAttribute('aria-hidden', 'true');
                elt.insertBefore(spinner, elt.firstChild);
            }
        }
    });

    document.addEventListener('htmx:afterRequest', function(evt) {
        const elt = evt.detail.elt;
        if (elt && (elt.tagName === 'BUTTON' || elt.tagName === 'A')) {
            elt.classList.remove('disabled');
            if (elt.tagName === 'BUTTON') elt.disabled = false;
            const spinner = elt.querySelector('.btn-htmx-spinner');
            if (spinner) spinner.remove();
        }
    });
    