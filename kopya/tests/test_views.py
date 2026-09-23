import os
import pickle

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from kopya import presenters, runner
from kopya.models import KopyaAnalysis, KopyaUpload
from kopya.tests.conftest import N_STUDENTS, make_optik_batch

pytestmark = pytest.mark.django_db


def _xlsx(content: bytes, name="sinav.xlsx"):
    return SimpleUploadedFile(
        name, content,
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


def _upload_and_confirm(client, workbook_bytes):
    resp = client.post(reverse("kopya:excel_upload"), {"file": _xlsx(workbook_bytes)})
    assert resp.status_code == 200
    uid = client.session[ "kopya_upload_uid"]
    return resp, uid, client.post(reverse("kopya:excel_analyze"), {"uid": uid})


# ── Giriş zorunluluğu ─────────────────────────────────────────────────────

@pytest.mark.parametrize("name,args", [
    ("kopya:index", []), ("kopya:excel_upload", []), ("kopya:excel_template", []),
    ("kopya:panel", ["batch_x"]), ("kopya:pair_detail", ["batch_x", "a", "b"]),
])
def test_login_required(client, name, args):
    resp = client.get(reverse(name, args=args))
    assert resp.status_code == 302 and "next=" in resp["Location"]


# ── Excel akışı ───────────────────────────────────────────────────────────

def test_template_download(client, owner):
    client.force_login(owner)
    resp = client.get(reverse("kopya:excel_template"))
    assert resp.status_code == 200
    assert "kopya_analizi_sablon.xlsx" in resp["Content-Disposition"]
    from kopya.engine.excel_upload import read_excel
    assert read_excel(resp.content).validation.ok


def test_upload_form(client, owner):
    client.force_login(owner)
    resp = client.get(reverse("kopya:excel_upload"))
    assert resp.status_code == 200
    assert "Yükle ve Doğrula" in resp.content.decode()


def test_upload_flow_end_to_end(client, owner, workbook_bytes, settings):
    client.force_login(owner)
    resp = client.post(reverse("kopya:excel_upload"), {"file": _xlsx(workbook_bytes)})
    html = resp.content.decode()
    assert "Yükleme Doğrulandı" in html and "Önizleme (ilk 10 satır)" in html
    uid = client.session["kopya_upload_uid"]
    staged = os.path.join(settings.MEDIA_ROOT, "kopya", "staging", f"{uid}.xlsx")
    assert os.path.exists(staged)
    assert KopyaUpload.objects.count() == 0  # onaydan önce kayıt yok

    resp = client.post(reverse("kopya:excel_analyze"), {"uid": uid})
    upload_id = "xl_" + uid
    assert resp.status_code == 302
    assert resp["Location"] == reverse("kopya:panel", args=[upload_id])
    up = KopyaUpload.objects.get(upload_id=upload_id)
    assert up.owner == owner and up.meta["n_students"] == N_STUDENTS
    assert up.meta["uploaded_by"] == str(owner.pk) and up.meta["source"] == "excel"
    assert not os.path.exists(staged)
    assert KopyaAnalysis.objects.filter(source_id=upload_id).count() == 1

    resp = client.get(resp["Location"])
    html = resp.content.decode()
    assert resp.status_code == 200
    for text in ("istatistiksel şüphe işaretidir", "Yönlü Çift", "En Şüpheli 10 Çift",
                 "Şans referansı", "Birincil — Komşu Çiftler", "Oturma filtresi"):
        assert text in html, text

    # Liste sayfasında görünür ve "Hesaplandı"
    html = client.get(reverse("kopya:index")).content.decode()
    assert "Excel Yüklemeleri" in html and "Hesaplandı" in html


def test_upload_invalid_file_shows_errors(client, owner):
    client.force_login(owner)
    resp = client.post(reverse("kopya:excel_upload"), {"file": _xlsx(b"bozuk dosya")})
    html = resp.content.decode()
    assert "Yükleme Başarısız" in html and "Engelleyici Hatalar" in html
    assert "kopya_upload_uid" not in client.session


def test_upload_too_large(client, owner, monkeypatch):
    from kopya import views
    monkeypatch.setattr(views, "MAX_UPLOAD_BYTES", 10)
    client.force_login(owner)
    resp = client.post(reverse("kopya:excel_upload"), {"file": _xlsx(b"x" * 100)})
    assert resp.status_code == 400 and "20 MB" in resp.content.decode()


def test_upload_analyze_uid_mismatch(client, owner, workbook_bytes):
    client.force_login(owner)
    client.post(reverse("kopya:excel_upload"), {"file": _xlsx(workbook_bytes)})
    resp = client.post(reverse("kopya:excel_analyze"), {"uid": "0123456789abcdef"})
    assert resp.status_code == 400
    assert "oturumu eşleşmedi" in resp.content.decode()
    assert KopyaUpload.objects.count() == 0


def test_upload_analyze_requires_post(client, owner):
    client.force_login(owner)
    assert client.get(reverse("kopya:excel_analyze")).status_code == 405


def test_excel_dashboard_after_restart(client, owner, workbook_bytes):
    """Kaynak hatası: bellekte olmayan xl_ batch KeyError veriyordu."""
    client.force_login(owner)
    _, uid, _ = _upload_and_confirm(client, workbook_bytes)
    KopyaAnalysis.objects.all().delete()   # "yeniden başlatma": sonuç yok
    runner._RESULT_LRU.clear()
    resp = client.get(reverse("kopya:panel", args=["xl_" + uid]))
    assert resp.status_code == 200 and "Birincil" in resp.content.decode()
    assert KopyaAnalysis.objects.filter(source_id="xl_" + uid).exists()


def test_excel_permissions(client, owner, other, admin_user, workbook_bytes):
    client.force_login(owner)
    _, uid, _ = _upload_and_confirm(client, workbook_bytes)
    url = reverse("kopya:panel", args=["xl_" + uid])
    client.force_login(other)
    assert client.get(url).status_code == 403
    assert client.get(reverse("kopya:pair_detail", args=["xl_" + uid, "20260000", "20260001"])).status_code == 403
    assert "Excel Yüklemeleri" not in client.get(reverse("kopya:index")).content.decode()
    assert client.get(reverse("kopya:panel", args=["xl_ffffffffffffffff"])).status_code == 404
    client.force_login(admin_user)
    assert client.get(url).status_code == 200


# ── Optik batch ───────────────────────────────────────────────────────────

def test_optik_dashboard_and_pair(client, owner):
    batch_id = make_optik_batch(owner)
    client.force_login(owner)
    resp = client.get(reverse("kopya:panel", args=[batch_id]))
    html = resp.content.decode()
    assert resp.status_code == 200
    assert "MAT101" in html and "Matematik I" in html
    pair_url = reverse("kopya:pair_detail", args=[batch_id, "20260001", "20260000"])
    assert f'href="{pair_url}?alpha=0.01"' in html  # <a> bağlantısı, onclick yok
    assert "window.location" not in html

    resp = client.get(pair_url + "?alpha=0.01")
    html = resp.content.decode()
    assert resp.status_code == 200
    for text in ("Madde Eşleşme Haritası", "İndeks Değerleri", "Bağlam", "Anahtar",
                 "U3 (anti-Guttman)", "komşu (Moore"):
        assert text in html, text


def test_top_n_keeps_alpha(client, owner):
    batch_id = make_optik_batch(owner)
    client.force_login(owner)
    resp = client.get(reverse("kopya:panel", args=[batch_id]), {"alpha": "0.05", "top_n": "5"})
    html = resp.content.decode()
    assert "En Şüpheli 5 Çift" in html
    assert "?alpha=0.05&amp;top_n=20" in html
    assert KopyaAnalysis.objects.filter(source_id=batch_id, alpha=0.05).exists()


def test_pair_not_found(client, owner):
    batch_id = make_optik_batch(owner)
    client.force_login(owner)
    resp = client.get(reverse("kopya:pair_detail", args=[batch_id, "yok", "20260000"]))
    assert resp.status_code == 404 and "Çift bulunamadı" in resp.content.decode()


def test_unscored_batch(client, owner):
    batch_id = make_optik_batch(owner, scored=False)
    client.force_login(owner)
    html = client.get(reverse("kopya:index")).content.decode()
    assert "Puanlanmamış" in html and "puanlanmadığı için analiz edilemez" in html
    resp = client.get(reverse("kopya:panel", args=[batch_id]))
    assert resp.status_code == 200 and "puanlama yapılmamış" in resp.content.decode()


def test_optik_permissions(client, owner, other, admin_user):
    batch_id = make_optik_batch(owner)
    client.force_login(other)
    assert client.get(reverse("kopya:panel", args=[batch_id])).status_code == 403
    assert client.get(reverse("kopya:panel", args=["batch_yok"])).status_code == 404
    assert "MAT101" not in client.get(reverse("kopya:index")).content.decode()
    client.force_login(admin_user)
    assert client.get(reverse("kopya:panel", args=[batch_id])).status_code == 200
    assert "MAT101" in client.get(reverse("kopya:index")).content.decode()


def test_index_grouping_and_states(client, owner):
    make_optik_batch(owner)
    client.force_login(owner)
    html = client.get(reverse("kopya:index")).content.decode()
    assert "2025-2026 / Güz" in html and "Şube 1" in html and "Hesapla" in html
    client.get(reverse("kopya:panel", args=["batch_kopya01"]))
    assert "Hesaplandı" in client.get(reverse("kopya:index")).content.decode()


def test_person_fit_alignment_with_excluded_student(client, owner):
    """Kaynak hatası: person_fit tam listedeki indeksle okunuyordu."""
    batch_id = make_optik_batch(owner, bad_booklet_index=2)
    client.force_login(owner)
    client.get(reverse("kopya:panel", args=[batch_id]))
    row = KopyaAnalysis.objects.get(source_id=batch_id)
    result = pickle.loads(bytes(row.result))
    ids = [str(s) for s in result.student_id]
    assert "20260002" not in ids and len(ids) == N_STUDENTS - 1

    sid = "20260005"                       # dışlanan öğrenciden sonra
    pos = ids.index(sid)                   # 4 (tam listede 5)
    expected = float(result.person_fit["U3"][pos])
    assert presenters.person_fit_value(result, "U3", sid) == pytest.approx(expected)

    resp = client.get(reverse("kopya:pair_detail", args=[batch_id, sid, "20260004"]))
    html = resp.content.decode()
    ctx_u3 = resp.context["u3_c"]
    assert ctx_u3 == presenters.fmt3(expected)
    assert f"Şüpheli: {ctx_u3}" in html


def test_computing_page_while_running(client, owner, settings, monkeypatch):
    import threading
    settings.KOPYA_SYNC = False
    batch_id = make_optik_batch(owner)
    gate = threading.Event()
    monkeypatch.setattr(runner, "compute_and_store", lambda *a: gate.wait(5))
    client.force_login(owner)
    try:
        resp = client.get(reverse("kopya:panel", args=[batch_id]))
        html = resp.content.decode()
        assert resp.status_code == 200 and resp["Refresh"] == "3"
        assert "Hesaplanıyor" in html and 'http-equiv="refresh"' in html
        assert "Hesaplanıyor" in client.get(reverse("kopya:index")).content.decode()
    finally:
        gate.set()
