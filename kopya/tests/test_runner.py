import threading

import pytest

from kopya import runner
from kopya.engine._pairwise import _input_hash
from kopya.models import KopyaAnalysis
from kopya.tests.conftest import make_optik_batch

pytestmark = pytest.mark.django_db


def test_compute_and_store_persists_and_reuses(owner):
    batch_id = make_optik_batch(owner)
    data, _ = runner.load_source(batch_id)
    result = runner.compute_and_store(batch_id, 0.01, data)
    row = KopyaAnalysis.objects.get(source_id=batch_id)
    assert row.input_hash == _input_hash(data) and row.alpha == 0.01
    runner._RESULT_LRU.clear()
    again = runner.get_stored(batch_id, 0.01, _input_hash(data))
    assert again.input_hash == result.input_hash and len(again.pairs) == len(result.pairs)
    out = runner.get_or_compute(batch_id, 0.01)
    assert out.ready and KopyaAnalysis.objects.count() == 1


def test_get_or_compute_source_error(owner):
    batch_id = make_optik_batch(owner, scored=False)
    with pytest.raises(runner.SourceError, match="puanlama"):
        runner.get_or_compute(batch_id, 0.01)
    with pytest.raises(runner.SourceError, match="bulunamadı"):
        runner.get_or_compute("xl_0000000000000000", 0.01)


def test_background_dedupe_and_computing_state(owner, settings, monkeypatch):
    """Eş zamanlı istekler tek hesapta birleşir; bitene kadar 'hesaplanıyor'."""
    settings.KOPYA_SYNC = False
    batch_id = make_optik_batch(owner)
    gate = threading.Event()
    calls = []

    def fake_compute(source_id, alpha, data):
        calls.append(source_id)
        gate.wait(5)
        return "SONUC"

    monkeypatch.setattr(runner, "compute_and_store", fake_compute)
    out1 = runner.get_or_compute(batch_id, 0.01, timeout_s=0.05)
    out2 = runner.get_or_compute(batch_id, 0.01, timeout_s=0.05)
    assert not out1.ready and not out2.ready
    assert runner.is_in_progress(batch_id, 0.01)
    assert runner.analysis_states([batch_id]) == {batch_id: "running"}
    gate.set()
    fut = runner._IN_PROGRESS.get(runner._prog_key(batch_id, 0.01))
    if fut is not None:
        assert fut.result(5) == "SONUC"
    assert calls == [batch_id]
    assert not runner.is_in_progress(batch_id, 0.01)


def test_background_failure_reported(owner, settings, monkeypatch):
    settings.KOPYA_SYNC = False
    batch_id = make_optik_batch(owner)

    def boom(source_id, alpha, data):
        raise ValueError("patladı")

    monkeypatch.setattr(runner, "compute_and_store", boom)
    with pytest.raises(runner.SourceError, match="patladı"):
        runner.get_or_compute(batch_id, 0.02, timeout_s=2)


def _rescore(batch_id, change_answer=True):
    """Yeniden puanlamayı taklit et: scored_at ilerler, istenirse bir cevap değişir."""
    from django.utils import timezone
    from optik import store
    scores = store.load_scores(batch_id)
    if change_answer:
        item = scores["records"][0]["item_scores"]["Q1"]
        item["student_answer"] = "E" if item["student_answer"] != "E" else "D"
    scores["scored_at"] = (timezone.now() + timezone.timedelta(seconds=1)).isoformat()
    store.save_scores(batch_id, scores)


def test_new_result_replaces_stale_results(owner):
    batch_id = make_optik_batch(owner)
    data, _ = runner.load_source(batch_id)
    runner.compute_and_store(batch_id, 0.01, data)
    _rescore(batch_id)
    new_data, _ = runner.load_source(batch_id)
    runner.compute_and_store(batch_id, 0.01, new_data)
    rows = list(KopyaAnalysis.objects.filter(source_id=batch_id))
    assert [r.input_hash for r in rows] == [_input_hash(new_data)]


def test_state_returns_to_none_after_rescoring(owner):
    batch_id = make_optik_batch(owner)
    data, _ = runner.load_source(batch_id)
    runner.compute_and_store(batch_id, 0.01, data)
    assert runner.analysis_states([batch_id]) == {batch_id: "done"}
    _rescore(batch_id, change_answer=False)
    assert runner.analysis_states([batch_id]) == {batch_id: "none"}
