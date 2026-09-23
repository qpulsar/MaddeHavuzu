"""Kopya Analizi test fikstürleri (küçük n: hızlı)."""
import io

import numpy as np
import pytest
from django.contrib.auth.models import User
from openpyxl import Workbook

from optik import store

N_STUDENTS = 14
N_ITEMS = 12
LETTERS = "ABCDE"


@pytest.fixture(autouse=True)
def kopya_settings(settings, tmp_path):
    settings.KOPYA_SYNC = True
    settings.MEDIA_ROOT = str(tmp_path / "media")
    from kopya import runner
    runner._RESULT_LRU.clear()
    yield settings
    runner._RESULT_LRU.clear()


@pytest.fixture
def owner(db):
    return User.objects.create_user(username="hoca", password="pw12345!")


@pytest.fixture
def other(db):
    return User.objects.create_user(username="baska", password="pw12345!")


@pytest.fixture
def admin_user(db):
    return User.objects.create_user(username="yonetici", password="pw12345!", is_staff=True)


def _simulated(seed=7, n=N_STUDENTS, m=N_ITEMS):
    """Anahtar + yanıt matrisi (1..5, arada boş); öğrenci 1, 0'ı kopyalar."""
    rng = np.random.default_rng(seed)
    key = rng.integers(1, 6, m)
    resp = np.where(rng.random((n, m)) < 0.6, key, rng.integers(1, 6, (n, m)))
    resp[rng.random((n, m)) < 0.05] = 0
    resp[1] = resp[0]
    return key, resp


def seat(i):
    return f"{chr(ord('A') + i // 4)}{i % 4 + 1}"


def make_workbook_bytes(seed=7, n=N_STUDENTS, m=N_ITEMS) -> bytes:
    key, resp = _simulated(seed, n, m)
    wb = Workbook()
    ws = wb.active
    ws.title = "Yanitlar"
    ws.append(["ogrenci_no", "ad_soyad", "salon", "oturma_kodu", "gozetmen_onayi", "kitapcik"]
              + [f"S{j+1}" for j in range(m)])
    for i in range(n):
        ws.append([f"2026{i:04d}", f"Öğrenci {i+1}", "Salon-A", seat(i), "E", "1"]
                  + [LETTERS[v - 1] if v else "" for v in resp[i]])
    ws2 = wb.create_sheet("Anahtar")
    ws2.append(["madde_no", "dogru_cevap"])
    for j in range(m):
        ws2.append([j + 1, LETTERS[key[j] - 1]])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


@pytest.fixture
def workbook_bytes():
    return make_workbook_bytes()


def make_optik_batch(user, test_id="test_kopya01", batch_id="batch_kopya01",
                     scored=True, bad_booklet_index=None, seed=7):
    """optik.store ile puanlanmış bir batch oluştur."""
    key, resp = _simulated(seed)
    qids = [f"Q{j+1}" for j in range(N_ITEMS)]
    store.save_test(test_id, {
        "created_by": user.id,
        "course_code": "MAT101", "course_name": "Matematik I", "exam_type": "Vize",
        "academic_year": "2025-2026", "semester": "guz",
        "answer_keys": {"A": {q: LETTERS[key[j] - 1] for j, q in enumerate(qids)}},
    })
    store.save_batch(batch_id, {"test_id": test_id, "batch_name": "Şube 1", "record_count": N_STUDENTS})
    if scored:
        records = []
        for i in range(N_STUDENTS):
            records.append({
                "student_no": f"2026{i:04d}",
                "booklet": "Z" if i == bad_booklet_index else "A",
                "seating": {"cell_id": seat(i)},
                "item_scores": {q: {"student_answer": LETTERS[resp[i][j] - 1] if resp[i][j] else ""}
                                for j, q in enumerate(qids)},
            })
        store.save_scores(batch_id, {"records": records})
    return batch_id
