"""
Sidebar etkin-bağlantı çakışması.

base.html'deki eski bağlantılar etkinliği `url_name in 'a,b,c'` (alt dize)
ve `url_name == 'dashboard'` ile belirler. Yeni uygulamaların URL adları bu
dizelerin içinde geçerse başka menüler de etkin görünür.
"""
import re
from pathlib import Path

from django.conf import settings

import kopya.urls
import optik.urls


def test_new_url_names_do_not_activate_old_sidebar_links():
    html = (Path(settings.BASE_DIR) / "templates" / "base.html").read_text(encoding="utf-8")
    checks = re.findall(r"url_name (?:in|==) '([^']+)'", html)
    assert checks
    names = [p.name for mod in (optik.urls, kopya.urls) for p in mod.urlpatterns]
    clashes = [(n, s) for s in checks for n in names if n in s]
    assert clashes == []
