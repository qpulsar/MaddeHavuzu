// Palet seçildiğinde anında önizleme
document.querySelectorAll('.palette-radio').forEach(radio => {
    radio.addEventListener('change', function() {
        if (this.checked) {
            document.documentElement.setAttribute('data-palette', this.value);
            // Sunucuya kaydet (anında)
            const form = document.getElementById('profileForm');
            const url = form ? form.getAttribute('data-url') : '';
            const csrf = form ? form.getAttribute('data-csrf') : '';
            fetch(url, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrf
                },
                body: JSON.stringify({ color_palette: this.value })
            });
        }
    });
});

// Tema modu seçildiğinde anında önizleme
document.querySelectorAll('.theme-radio').forEach(radio => {
    radio.addEventListener('change', function() {
        if (this.checked) {
            document.documentElement.setAttribute('data-theme', this.value);
            // Topbar ikonunu güncelle
            const icon = document.getElementById('themeIcon');
            if (icon) {
                if (this.value === 'dark') icon.className = 'bi bi-moon-fill';
                else if (this.value === 'system') icon.className = 'bi bi-circle-half';
                else icon.className = 'bi bi-sun-fill';
            }
            // Sunucuya kaydet (anında)
            const form = document.getElementById('profileForm');
            const url = form ? form.getAttribute('data-url') : '';
            const csrf = form ? form.getAttribute('data-csrf') : '';
            fetch(url, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrf
                },
                body: JSON.stringify({ theme: this.value })
            });
        }
    });
});