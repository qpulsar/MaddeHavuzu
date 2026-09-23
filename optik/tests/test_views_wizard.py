"""Sihirbaz sayfaları (test, form yükleme, cevap anahtarı, eski batch sayfaları) view testleri."""
import io
import json
import os
from datetime import date
from unittest import mock

import pytest
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import NoReverseMatch, reverse, reverse_lazy
from openpyxl import Workbook

from optik import store
from optik.models import OptikTest
from optik.services import core
from optik.views import testler as tests_views

pytestmark = pytest.mark.django_db
LOGIN = reverse_lazy("login")


# ── Fixture'lar ─────────────────────────────────────────────────────────

@pytest.fixture
def other(db):
    return User.objects.create_user(username="baskasi", password="x")


@pytest.fixture
def admin_user(db):
    return User.objects.create_user(username="yonetici", password="x", is_staff=True)


@pytest.fixture
def owner_client(client, user):
    client.force_login(user)
    return client


@pytest.fixture
def test_id(user):
    return core.create_test("MAT101", "Matematik", "Vize", ["A", "B"], 5, user,
                            academic_year="2025-2026", semester="Güz")


@pytest.fixture
def batch_id(test_id, user):
    return core.create_batch(test_id, "Şube 1", user)


def _login(client, u):
    client.force_login(u)
    return client


def _png(name="form.png", content=b"\x89PNG\r\n\x1a\nfake"):
    return SimpleUploadedFile(name, content, content_type="image/png")


VALID_FORM = {
    "course_code": "fiz102", "course_name": "Fizik", "exam_type": "Final",
    "academic_year": "2025-2026", "semester": "Bahar", "booklets": ["A", "B"],
    "mcq_count": "10", "open_count": "2", "mcq_points": "80", "open_points": "20",
}


# ── Yetki matrisi ───────────────────────────────────────────────────────

TEST_GET_URLS = ["test_detail", "test_edit", "upload_forms", "answer_key",
                 "answer_key_upload"]
TEST_POST_URLS = ["test_remove_approval", "save_answer_key",
                  "save_all_answer_keys", "auto_save_answer_keys", "save_item_points",
                  "save_detailed_points", "save_booklet_mapping"]
BATCH_GET_URLS = ["progress", "progress_api", "batch_detail"]


@pytest.mark.parametrize("name", TEST_GET_URLS + TEST_POST_URLS)
def test_test_views_require_login(client, test_id, name):
    method = client.post if name in TEST_POST_URLS else client.get
    resp = method(reverse(f"optik:{name}", args=[test_id]))
    assert resp.status_code == 302 and resp["Location"].startswith(str(LOGIN))


@pytest.mark.parametrize("name", TEST_GET_URLS + TEST_POST_URLS)
def test_test_views_forbid_other_user(client, test_id, other, name):
    _login(client, other)
    method = client.post if name in TEST_POST_URLS else client.get
    resp = method(reverse(f"optik:{name}", args=[test_id]))
    assert resp.status_code == 403


@pytest.mark.parametrize("name", ["test_edit", "upload_forms", "answer_key", "answer_key_upload"])
def test_test_views_unknown_test_404(owner_client, name):
    assert owner_client.get(reverse(f"optik:{name}", args=["test_yok"])).status_code == 404


@pytest.mark.parametrize("name", BATCH_GET_URLS)
def test_batch_views_login_and_ownership(client, batch_id, other, name):
    url = reverse(f"optik:{name}", args=[batch_id])
    resp = client.get(url)
    assert resp.status_code == 302 and resp["Location"].startswith(str(LOGIN))
    _login(client, other)
    assert client.get(url).status_code == 403


@pytest.mark.parametrize("name", ["index", "test_new"])
def test_global_pages_require_login(client, name):
    resp = client.get(reverse(f"optik:{name}"))
    assert resp.status_code == 302 and resp["Location"].startswith(str(LOGIN))


def test_admin_can_access_other_users_test(client, test_id, admin_user):
    _login(client, admin_user)
    assert client.get(reverse("optik:answer_key", args=[test_id])).status_code == 200


# ── Ana sayfa ───────────────────────────────────────────────────────────

def test_index_lists_only_own_tests_grouped(owner_client, user, other, test_id):
    core.create_test("BAS1", "Başkasının", "Vize", ["A"], 3, other)
    core.create_test("ESK1", "Eski", "Final", ["A"], 3, user)  # yıl/dönem yok → Diğer
    resp = owner_client.get(reverse("optik:index"))
    assert resp.status_code == 200
    html = resp.content.decode()
    assert "MAT101 - Vize" in html and "ESK1 - Final" in html
    assert "BAS1" not in html
    labels = [g["label"] for g in resp.context["groups"]]
    assert labels == ["2025-2026 / Güz", "Diğer"]
    assert "Hazırlanıyor" in html
    assert "Tüm Öğretim Elemanları" not in html  # filtre yalnızca yönetici için


def test_index_status_badges(owner_client, test_id, batch_id):
    html = owner_client.get(reverse("optik:index")).content.decode()
    assert "Form Yüklendi" in html and reverse("optik:scoring", args=[test_id]) in html
    store.save_scores(batch_id, {"students": []})
    html = owner_client.get(reverse("optik:index")).content.decode()
    assert "Puanlandı" in html and reverse("kopya:panel", args=[batch_id]) not in html
    assert "Yayın" not in html


def test_group_sort_order(user):
    for ay, sem in [("2024-2025", "Bahar"), ("2025-2026", "Bahar"), ("2025-2026", "Güz"),
                    ("2025-2026", "Yaz")]:
        core.create_test("X", "X", "Vize", ["A"], 1, user, academic_year=ay, semester=sem)
    groups = tests_views.group_test_cards(OptikTest.objects.prefetch_related("batches"), False)
    assert [g["label"] for g in groups] == [
        "2025-2026 / Güz", "2025-2026 / Bahar", "2025-2026 / Yaz", "2024-2025 / Bahar"]


def test_index_admin_instructor_filter(client, admin_user, user, other, test_id):
    core.create_test("BAS1", "Başkasının", "Vize", ["A"], 3, other)
    _login(client, admin_user)
    html = client.get(reverse("optik:index")).content.decode()
    assert "MAT101" in html and "BAS1" in html
    assert "Tüm Öğretim Elemanları" in html and "Şükrü Işık" in html  # oluşturan adı
    html = client.get(reverse("optik:index"), {"instructor": str(other.pk)}).content.decode()
    assert "BAS1" in html and "MAT101" not in html
    assert client.get(reverse("optik:index"), {"instructor": "abc"}).status_code == 200


def test_index_escapes_user_data(owner_client, user):
    core.create_test("<script>x</script>", "Ad", "Vize", ["A"], 1, user)
    html = owner_client.get(reverse("optik:index")).content.decode()
    assert "<script>x</script>" not in html and "&lt;script&gt;" in html


# ── Test oluşturma / düzenleme ─────────────────────────────────────────

def test_academic_year_and_semester_defaults():
    assert tests_views.current_academic_year(date(2026, 9, 23)) == "2026-2027"
    assert tests_views.current_academic_year(date(2026, 3, 1)) == "2025-2026"
    assert tests_views.current_semester(date(2026, 10, 1)) == "Güz"
    assert tests_views.current_semester(date(2027, 1, 10)) == "Güz"
    assert tests_views.current_semester(date(2026, 4, 1)) == "Bahar"
    assert tests_views.current_semester(date(2026, 7, 15)) == "Yaz"


def test_test_new_prefill(owner_client):
    resp = owner_client.get(reverse("optik:test_new"),
                            {"course_code": "PDN1001", "course_name": "Ölçme", "exam_type": "Final"})
    assert resp.status_code == 200
    html = resp.content.decode()
    assert 'value="PDN1001"' in html and "readonly" in html
    assert '<input type="hidden" name="exam_type" value="Final">' in html
    assert resp.context["form"]["academic_year"] == tests_views.current_academic_year()


def test_test_create_success(owner_client, user):
    resp = owner_client.post(reverse("optik:test_create"), VALID_FORM)
    obj = OptikTest.objects.get(course_code="FIZ102")
    assert resp.status_code == 302
    assert resp["Location"] == reverse("optik:upload_forms", args=[obj.test_id])
    assert obj.owner == user and obj.semester == "Bahar" and obj.academic_year == "2025-2026"
    t = core.get_test(obj.test_id)
    assert t["num_items"] == 12 and t["booklets"] == ["A", "B"]
    assert t["items"]["Q1"] == {"type": "MCQ", "points": 8.0}
    assert t["items"]["Q12"] == {"type": "OPEN", "points": 10.0}


@pytest.mark.parametrize("override, message", [
    ({"mcq_points": "70"}, "Toplam puan 100 olmalıdır"),
    ({"booklets": []}, "En az bir kitapçık"),
    ({"mcq_count": "0", "open_count": "0"}, "En az bir soru"),
    ({"open_count": "0"}, "Açık uçlu madde sayısı 0"),
    ({"mcq_count": "x"}, "tam sayı"),
    ({"course_code": ""}, "Ders kodu zorunludur"),
])
def test_test_create_validation(owner_client, override, message):
    data = dict(VALID_FORM, **override)
    resp = owner_client.post(reverse("optik:test_create"), data)
    assert resp.status_code == 400
    assert message in resp.content.decode()
    assert not OptikTest.objects.exists()


def test_test_create_requires_post(owner_client):
    assert owner_client.get(reverse("optik:test_create")).status_code == 405


def test_test_detail_redirects_to_edit(owner_client, test_id):
    resp = owner_client.get(reverse("optik:test_detail", args=[test_id]))
    assert resp.status_code == 302 and resp["Location"] == reverse("optik:test_edit", args=[test_id])


def test_test_edit_get_and_post(owner_client, test_id):
    resp = owner_client.get(reverse("optik:test_edit", args=[test_id]))
    assert resp.status_code == 200 and resp.context["wizard_step"] == 1
    assert 'value="MAT101"' in resp.content.decode()
    data = dict(VALID_FORM, course_code="mat102", booklets=["A"], mcq_count="4",
                open_count="0", mcq_points="100", open_points="0")
    resp = owner_client.post(reverse("optik:test_edit", args=[test_id]), data)
    assert resp.status_code == 302 and resp["Location"] == reverse("optik:upload_forms", args=[test_id])
    t = core.get_test(test_id)
    assert t["course_code"] == "MAT102" and t["num_items"] == 4 and t["semester"] == "Bahar"
    assert t["items"]["Q4"]["points"] == 25.0 and "Q5" not in t["items"]


def test_test_edit_validation(owner_client, test_id):
    data = dict(VALID_FORM, mcq_points="50")
    resp = owner_client.post(reverse("optik:test_edit", args=[test_id]), data)
    assert resp.status_code == 400 and "Toplam puan 100" in resp.content.decode()
    assert core.get_test(test_id)["course_code"] == "MAT101"


def test_approved_test_read_only_and_remove_approval(owner_client, test_id):
    core.set_test_approval(test_id, True)
    resp = owner_client.get(reverse("optik:test_edit", args=[test_id]))
    assert resp.status_code == 200 and "Onaylı test düzenlenemez" in resp.content.decode()
    resp = owner_client.post(reverse("optik:test_edit", args=[test_id]), VALID_FORM)
    assert resp.status_code == 403
    assert owner_client.get(reverse("optik:test_remove_approval", args=[test_id])).status_code == 405
    resp = owner_client.post(reverse("optik:test_remove_approval", args=[test_id]))
    assert resp.status_code == 302 and resp["Location"] == reverse("optik:test_detail", args=[test_id])
    assert not core.get_test(test_id)["is_approved"]


# ── Form yükleme ────────────────────────────────────────────────────────

def test_upload_forms_page(owner_client, test_id):
    resp = owner_client.get(reverse("optik:upload_forms", args=[test_id]))
    assert resp.status_code == 200 and resp.context["wizard_step"] == 2
    html = resp.content.decode()
    assert "111111111111" in html and "TXT Yükleme" not in html
    assert resp.context["batch_name"] == "2025-2026/MAT101/Vize"


def test_txt_upload_removed(client, admin_user, test_id):
    """TXT yükleme tamamen kaldırıldı: yöneticiye de sekme yok, eski adres 404."""
    _login(client, admin_user)
    html = client.get(reverse("optik:upload_forms", args=[test_id])).content.decode()
    assert "TXT" not in html and "txt_file" not in html
    with pytest.raises(NoReverseMatch):
        reverse("optik:upload_txt", args=[test_id])
    url = f"/optik/test/{test_id}/upload-txt/"
    assert client.post(url, {"txt_file": SimpleUploadedFile("s.txt", b"x")}).status_code == 404
    assert core.get_test_batch_id(test_id) is None


def test_upload_forms_post_saves_files_and_starts_processing(owner_client, test_id, user):
    files = [_png("a.png"), _png("../../evil b.JPG"), _png("not.txt"), _png("empty.png", b"")]
    with mock.patch("optik.services.background.start_processing") as sp:
        resp = owner_client.post(reverse("optik:upload_forms", args=[test_id]), {"files": files})
    batch_id = core.get_test_batch_id(test_id)
    assert batch_id
    assert resp.status_code == 302
    assert resp["Location"] == reverse("optik:progress", args=[batch_id])
    sp.assert_called_once()
    args, kwargs = sp.call_args
    assert args[0] == batch_id and kwargs["user"] == user
    paths = args[1]
    upload_dir = store.get_upload_dir(batch_id)
    assert len(paths) == 2
    for p in paths:
        assert os.path.dirname(p) == upload_dir and os.path.isfile(p)
        assert ".." not in os.path.basename(p)
    names = sorted(os.path.basename(p)[9:] for p in paths)
    assert names == ["a.png", "evil_b.JPG"]


def test_upload_forms_post_errors(owner_client, test_id):
    url = reverse("optik:upload_forms", args=[test_id])
    with mock.patch("optik.services.background.start_processing") as sp:
        resp = owner_client.post(url, {})
        assert resp.status_code == 302 and resp["Location"] == url
        resp = owner_client.post(url, {"files": [_png("x.gif")]}, follow=True)
        assert "Geçerli dosya yok" in resp.content.decode()
    sp.assert_not_called()


def test_upload_forms_blocked_for_approved_test(owner_client, test_id):
    core.set_test_approval(test_id, True)
    url = reverse("optik:upload_forms", args=[test_id])
    assert owner_client.get(url).status_code == 403
    with mock.patch("optik.services.background.start_processing") as sp:
        assert owner_client.post(url, {"files": [_png()]}).status_code == 403
    sp.assert_not_called()


# ── İlerleme ────────────────────────────────────────────────────────────

def test_progress_page_and_api(owner_client, test_id, batch_id):
    url = reverse("optik:progress", args=[batch_id])
    resp = owner_client.get(url)
    assert resp.status_code == 200
    assert resp.context["next_url"] == reverse("optik:answer_key", args=[test_id])
    assert resp.context["retry_url"] == reverse("optik:upload_forms", args=[test_id])

    store.update_batch_fields(batch_id, status="COMPLETED_WITH_ERRORS", progress={
        "total_files": 3, "processed": 3, "success": 2, "failed": 1, "progress_percentage": 100})
    data = owner_client.get(reverse("optik:progress_api", args=[batch_id])).json()
    assert data["status"] == "COMPLETED_WITH_ERRORS" and data["is_complete"] is True
    assert data["total_files"] == 3 and data["success"] == 2 and data["failed"] == 1
    assert data["progress_percentage"] == 100 and data["errors"] == []


# ── Cevap anahtarı ──────────────────────────────────────────────────────

def test_answer_key_page_tabs(owner_client, test_id):
    core.set_answer_key(test_id, "A", {"Q1": "C", "Q2": "*"})
    url = reverse("optik:answer_key", args=[test_id])
    resp = owner_client.get(url)
    assert resp.status_code == 200 and resp.context["active_tab"] == "answers"
    assert resp.context["wizard_step"] == 3
    rows = resp.context["answer_rows"]
    assert len(rows) == 5 and rows[0]["cells"][0]["value"] == "C"
    assert len(resp.context["mapping_rows"]) == 5  # A + B → eşleştirme tablosu
    html = resp.content.decode()
    assert 'name="answer_B_Q5"' in html and 'name="mapping_B_Q1"' in html and 'name="points_Q1"' in html
    assert owner_client.get(url, {"tab": "points"}).context["active_tab"] == "points"
    assert owner_client.get(url, {"tab": "kotu"}).context["active_tab"] == "answers"
    assert "&lt;b&gt;" in owner_client.get(url, {"success": "<b>ok</b>"}).content.decode()


def test_answer_key_open_items(owner_client, user):
    tid = core.create_test("X", "X", "Vize", ["A"], 3, user,
                           question_types={"MCQ": 2, "TF": 0, "OPEN": 1},
                           points_by_type={"MCQ": 80.0, "TF": 0.0, "OPEN": 20.0})
    resp = owner_client.get(reverse("optik:answer_key", args=[tid]))
    assert resp.context["answer_rows"][2]["is_open"] is True
    assert len(resp.context["open_points_rows"]) == 1
    assert resp.context["show_mapping"] is False
    assert 'name="answer_A_Q3"' not in resp.content.decode()


def test_save_all_answer_keys(owner_client, test_id):
    data = {"answer_A_Q1": "a", "answer_A_Q2": "*", "answer_A_Q3": "Z", "answer_B_Q1": "E",
            "answer_A_Q99": "B"}
    resp = owner_client.post(reverse("optik:save_all_answer_keys", args=[test_id]), data, follow=True)
    assert "2 kitapçık kaydedildi!" in resp.content.decode()
    keys = core.get_test(test_id)["answer_keys"]
    assert keys == {"A": {"Q1": "A", "Q2": "*"}, "B": {"Q1": "E"}}


def test_save_answer_key_single_booklet(owner_client, test_id):
    url = reverse("optik:save_answer_key", args=[test_id])
    resp = owner_client.post(url, {"save_booklet": "B", "answer_B_Q2": "D"})
    assert resp.status_code == 302
    assert core.get_test(test_id)["answer_keys"]["B"] == {"Q2": "D"}
    resp = owner_client.post(url, {}, follow=True)
    assert "Kitapçık seçilmedi" in resp.content.decode()
    owner_client.post(url, {"save_booklet": "Q", "answer_Q_Q1": "A"})
    assert "Q" not in core.get_test(test_id)["answer_keys"]


def test_auto_save_answer_keys_json(owner_client, test_id):
    url = reverse("optik:auto_save_answer_keys", args=[test_id])
    resp = owner_client.post(url, json.dumps({"answer_A_Q1": "b", "answer_B_Q5": "C", "x": "y"}),
                             content_type="application/json")
    assert resp.status_code == 200 and resp.json()["ok"] is True
    keys = core.get_test(test_id)["answer_keys"]
    assert keys["A"] == {"Q1": "B"} and keys["B"] == {"Q5": "C"}
    resp = owner_client.post(url, "bozuk{", content_type="application/json")
    assert resp.status_code == 400 and resp.json()["ok"] is False


def test_auto_save_enforces_csrf(client, user, test_id):
    from django.test import Client
    c = Client(enforce_csrf_checks=True)
    c.force_login(user)
    resp = c.post(reverse("optik:auto_save_answer_keys", args=[test_id]), "{}",
                  content_type="application/json")
    assert resp.status_code == 403


def test_save_detailed_and_item_points(owner_client, test_id):
    data = {f"points_Q{i}": str(i * 2) for i in range(1, 6)}
    resp = owner_client.post(reverse("optik:save_detailed_points", args=[test_id]), data)
    assert resp["Location"] == reverse("optik:answer_key", args=[test_id]) + "?tab=points"
    assert core.get_test(test_id)["items"]["Q5"]["points"] == 10.0
    resp = owner_client.post(reverse("optik:save_detailed_points", args=[test_id]),
                             {"points_Q1": "abc"}, follow=True)
    assert "geçersiz puan" in resp.content.decode()
    assert core.get_test(test_id)["items"]["Q1"]["points"] == 2.0

    owner_client.post(reverse("optik:save_item_points", args=[test_id]), {"equal_points": "20"})
    assert all(i["points"] == 20.0 for i in core.get_test(test_id)["items"].values())


def test_save_booklet_mapping(owner_client, test_id):
    url = reverse("optik:save_booklet_mapping", args=[test_id])
    data = {f"mapping_B_Q{i}": str(6 - i) for i in range(1, 6)}
    owner_client.post(url, data)
    assert core.get_test(test_id)["booklet_mapping"] == {"B": {"Q1": 5, "Q2": 4, "Q3": 3, "Q4": 2, "Q5": 1}}
    resp = owner_client.post(url, dict(data, mapping_B_Q1="99"), follow=True)
    assert "geçersiz eşleştirme" in resp.content.decode()
    assert core.get_test(test_id)["booklet_mapping"]["B"]["Q1"] == 5


def _xlsx(rows):
    wb = Workbook()
    ws = wb.active
    for r in rows:
        ws.append(r)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_answer_key_excel_upload(owner_client, test_id):
    url = reverse("optik:answer_key_upload", args=[test_id])
    assert owner_client.get(url).status_code == 200
    content = _xlsx([["item", "booklet_A", "booklet_B", "points"],
                     ["Q1", "A", "C", 30], [2, "b", "D", 70]])
    resp = owner_client.post(url, {"file": SimpleUploadedFile("key.xlsx", content)})
    assert resp.status_code == 302 and resp["Location"] == reverse("optik:answer_key", args=[test_id])
    test = core.get_test(test_id)
    assert test["answer_keys"]["A"] == {"Q1": "A", "Q2": "B"}
    assert test["answer_keys"]["B"] == {"Q1": "C", "Q2": "D"}
    assert test["items"]["Q2"]["points"] == 70.0


def test_answer_key_excel_upload_errors(owner_client, test_id):
    url = reverse("optik:answer_key_upload", args=[test_id])
    resp = owner_client.post(url, {"file": SimpleUploadedFile("key.xlsx", _xlsx([["x", "A"], [1, "A"]]))})
    assert resp.status_code == 400 and "sütunu bulunamadı" in resp.content.decode()
    resp = owner_client.post(url, {"file": SimpleUploadedFile("key.xlsx", b"not a zip")})
    assert resp.status_code == 400 and "okunamadı" in resp.content.decode()
    resp = owner_client.post(url, {"file": SimpleUploadedFile("key.csv", b"a,b")})
    assert resp.status_code == 400
    assert owner_client.post(url, {}).status_code == 400


# ── Batch sayfası ───────────────────────────────────────────────────────

def test_batch_detail_redirects_to_records(owner_client, test_id, batch_id):
    resp = owner_client.get(reverse("optik:batch_detail", args=[batch_id]))
    assert resp.status_code == 302 and resp["Location"] == reverse("optik:records", args=[test_id])
