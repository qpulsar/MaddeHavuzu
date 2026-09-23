import numpy as np
import pytest

from kopya.adapter import AdapterError, _encode_letter, _sorted_qids, batch_to_exam_data
from kopya.engine.core import to_canonical_matrix
from kopya.tests.conftest import N_ITEMS, N_STUDENTS, make_optik_batch
from optik import store

pytestmark = pytest.mark.django_db


def test_encode_letter_rules():
    assert _encode_letter("a") == 1
    assert _encode_letter("E") == 5
    assert _encode_letter("") == 0
    assert _encode_letter("?") == 0
    assert _encode_letter(None) == 0
    assert _encode_letter("!") == -1
    assert _encode_letter("3") == 3
    with pytest.raises(AdapterError):
        _encode_letter("Z")


def test_sorted_qids_numeric():
    assert _sorted_qids(["Q10", "Q2", "Q1"]) == ["Q1", "Q2", "Q10"]


def test_batch_to_exam_data(owner):
    batch_id = make_optik_batch(owner)
    data, meta = batch_to_exam_data(batch_id)
    assert data.responses.shape == (N_STUDENTS, N_ITEMS)
    assert data.responses.dtype == np.int8
    assert data.key.min() >= 1
    assert data.permutation.shape == (1, N_ITEMS)
    assert data.student_id[0] == "20260000"
    assert data.seat_code[5] == "B2"
    assert data.excluded is None
    assert meta["course_code"] == "MAT101"
    assert meta["n_items"] == N_ITEMS
    assert meta["booklets"] == ["A"]
    assert meta["warnings"] == []


def test_unknown_booklet_excluded_with_warning(owner):
    batch_id = make_optik_batch(owner, bad_booklet_index=2)
    data, meta = batch_to_exam_data(batch_id)
    assert data.excluded is not None and data.excluded[2]
    assert any("bilinmeyen kitapçık" in w for w in meta["warnings"])


def test_unscored_batch_raises_turkish_message(owner):
    batch_id = make_optik_batch(owner, scored=False)
    with pytest.raises(AdapterError, match="puanlama yapılmamış"):
        batch_to_exam_data(batch_id)


def test_missing_batch():
    with pytest.raises(AdapterError, match="Batch bulunamadı"):
        batch_to_exam_data("batch_yok")


def _add_reversed_booklet_b(student_index):
    """B kitapçığı = A'nın ters sırası (booklet_mapping ile); bir öğrenci B'ye geçer."""
    test = store.load_test("test_kopya01")
    a_key = test["answer_keys"]["A"]
    test["answer_keys"]["B"] = {f"Q{p}": a_key[f"Q{N_ITEMS - p + 1}"] for p in range(1, N_ITEMS + 1)}
    test["booklet_mapping"] = {"B": {f"Q{p}": N_ITEMS - p + 1 for p in range(1, N_ITEMS + 1)}}
    store.save_test("test_kopya01", test)
    scores = store.load_scores("batch_kopya01")
    rec = scores["records"][student_index]
    original = [rec["item_scores"][f"Q{j}"]["student_answer"] for j in range(1, N_ITEMS + 1)]
    rec["booklet"] = "B"
    rec["item_scores"] = {f"Q{p}": {"student_answer": original[N_ITEMS - p]} for p in range(1, N_ITEMS + 1)}
    store.save_scores("batch_kopya01", scores)
    return original


def test_multi_booklet_uses_booklet_mapping(owner):
    make_optik_batch(owner)
    before, _ = batch_to_exam_data("batch_kopya01")
    _add_reversed_booklet_b(3)
    data, meta = batch_to_exam_data("batch_kopya01")
    assert meta["booklets"] == ["A", "B"]
    assert list(data.permutation[1]) == list(range(N_ITEMS - 1, -1, -1))
    # B'deki öğrencinin kanonik (A sırası) cevapları değişmemeli
    canon = lambda d: to_canonical_matrix(d.responses, d.booklet, d.permutation)
    assert (canon(data)[3] == canon(before)[3]).all()
    assert (data.key == before.key).all()


def test_multi_booklet_without_mapping_is_identity(owner):
    make_optik_batch(owner)
    test = store.load_test("test_kopya01")
    test["answer_keys"]["B"] = dict(test["answer_keys"]["A"])
    store.save_test("test_kopya01", test)
    data, _ = batch_to_exam_data("batch_kopya01")
    assert (data.permutation == np.arange(N_ITEMS)).all()


def test_multi_booklet_duplicate_mapping_rejected(owner):
    make_optik_batch(owner)
    _add_reversed_booklet_b(3)
    test = store.load_test("test_kopya01")
    test["booklet_mapping"]["B"]["Q2"] = test["booklet_mapping"]["B"]["Q1"]
    store.save_test("test_kopya01", test)
    with pytest.raises(AdapterError, match="aynı A maddesi"):
        batch_to_exam_data("batch_kopya01")


def test_multi_booklet_key_mismatch_rejected(owner):
    make_optik_batch(owner)
    _add_reversed_booklet_b(3)
    test = store.load_test("test_kopya01")
    q1 = test["answer_keys"]["B"]["Q1"]
    test["answer_keys"]["B"]["Q1"] = "B" if q1 != "B" else "C"
    store.save_test("test_kopya01", test)
    with pytest.raises(AdapterError, match="eşleştiği A kitapçığı"):
        batch_to_exam_data("batch_kopya01")


def test_faulty_key_items_dropped_with_warning(owner):
    make_optik_batch(owner)
    before, _ = batch_to_exam_data("batch_kopya01")
    test = store.load_test("test_kopya01")
    test["answer_keys"]["A"]["Q3"] = "*"
    test["answer_keys"]["A"]["Q7"] = ""
    store.save_test("test_kopya01", test)
    data, meta = batch_to_exam_data("batch_kopya01")
    keep = [j for j in range(N_ITEMS) if j not in (2, 6)]
    assert data.responses.shape == (N_STUDENTS, N_ITEMS - 2)
    assert (data.key == before.key[keep]).all()
    assert (data.responses == before.responses[:, keep]).all()
    assert meta["n_items"] == N_ITEMS - 2
    assert any("Q3, Q7" in w for w in meta["warnings"])
