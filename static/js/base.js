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
                overlay.classList.add('show');
                // 15 saniye sonra otomatik kapat (dosya inmeye başlamış olmalı veya başarısız olmuştur)
                setTimeout(() => {
                    overlay.classList.remove('show');
                }, 15000);
            }
        }
    });
    