import numpy as np

from kopya import presenters as P
from kopya.engine.core import IndexValue, PairResult


def iv(p_raw, p_adj=None, status="OK", value=1.0):
    return IndexValue(value=value, p_raw=p_raw, p_adjusted=p_adj, status=status)


def pair(c, s, tier="primary", cw=0, **indices):
    return PairResult(copier_id=c, source_id=s, same_booklet=True, indices=indices,
                      descriptive={"common_wrong": cw}, tier=tier)


def test_parse_alpha_and_top_n():
    assert P.parse_alpha(None) == 0.01
    assert P.parse_alpha("0.05") == 0.05
    assert P.parse_alpha("abc") == 0.01
    assert P.parse_alpha("2") == 0.01
    assert P.parse_alpha("nan") == 0.01
    assert P.parse_top_n(None) == 10
    assert P.parse_top_n("0") == 1
    assert P.parse_top_n("500") == 50
    assert P.parse_top_n("x") == 10


def test_fmt_p_semantics():
    assert P.fmt_p(None, 0.01) == {"text": "-", "cls": "na", "title": ""}
    assert P.fmt_p(iv(None, status="NOT_COMPUTABLE", value=None), 0.01)["text"] == "-"
    hit = P.fmt_p(iv(0.0001, 0.004), 0.01)
    assert hit["cls"] == "hit" and hit["text"] == "0.0001" and "0.0040" in hit["title"]
    miss = P.fmt_p(iv(0.0001, 0.2), 0.01)
    assert miss["cls"] == "" and miss["text"] == "0.0001"
    desc = P.fmt_p(iv(0.0001, 0.0001, status="DESCRIPTIVE_ONLY"), 0.01)
    assert desc["cls"] == "na" and desc["text"] == "0.0001"
    assert P.fmt_p(iv(0.3, None), 0.01)["title"] == "p_adj: hesaplanmadı"


def test_hit_count_ignores_descriptive():
    ivs = [iv(0.001, 0.001), iv(0.001, 0.001, status="DESCRIPTIVE_ONLY"),
           iv(0.5, 0.5), None, iv(0.001, None)]
    assert P.hit_count(ivs, 0.01) == 2


def test_rank_top_suspicious_couples_and_min():
    pairs = [
        pair("a", "b", K1=iv(0.2), S1=iv(0.05)),
        pair("b", "a", K1=iv(0.01)),          # aynı ikili, daha küçük p
        pair("a", "c", K_star=iv(0.001)),
        pair("c", "a", K2=iv(0.5)),
        pair("b", "c", K=iv(0.00001)),         # K top-N'e girmez
    ]
    top = P.rank_top_suspicious(pairs, 10)
    assert [(p, name, pr.copier_id) for p, name, pr in top] == [
        (0.001, "K_star", "a"), (0.01, "K1", "b")]
    assert len(P.rank_top_suspicious(pairs, 1)) == 1


def test_chance_reference_tones():
    c = P.chance_reference(0.001, 99)  # beklenen 0.01, oran 0.1
    assert c["expected"] == "0.0100" and c["tone"] == "strong"
    assert "0.10× altında" == c["interp_bold"]
    assert P.chance_reference(0.007, 99)["tone"] == "weak"
    assert "uyumlu" in P.chance_reference(0.015, 99)["interp_lead"]
    assert "sıradan" in P.chance_reference(0.5, 99)["interp_lead"]
    assert P.chance_reference(None, 5) is None
    assert P.chance_reference(0.1, 0) is None


def test_top_context_keeps_urls_and_fdr_star():
    pairs = [pair("a", "b", cw=3, K1=iv(0.0001, 0.001))]
    ctx = P.top_suspicious_context(pairs, 5, 1, 0.01,
                                   pair_url=lambda c, s: f"/p/{c}/{s}",
                                   top_n_url=lambda n: f"?top_n={n}")
    row = ctx["rows"][0]
    assert row["fdr_hit"] and row["url"] == "/p/a/b" and row["common_wrong"] == 3
    assert [b["active"] for b in ctx["buttons"]] == [True, False, False]


def test_primary_table_sorted_by_hits():
    pairs = [pair("a", "b", K1=iv(0.5, 0.5)),
             pair("c", "d", K1=iv(0.001, 0.001), S1=iv(0.001, 0.001))]
    ctx = P.primary_table_context(pairs, 0.01, 2, pair_url=lambda c, s: None)
    assert [r["copier"] for r in ctx["rows"]] == ["c", "a"]
    assert ctx["rows"][0]["flags"] == 2
    assert len(ctx["rows"][0]["cells"]) == len(P.PROB_INDEX_ORDER)


def test_secondary_table_sort_and_limit():
    pairs = [pair(f"s{i}", "x", tier="secondary",
                  K1=iv(i / 1000 + 0.001, status="DESCRIPTIVE_ONLY")) for i in range(150)]
    pairs.append(pair("none", "x", tier="secondary"))
    ctx = P.secondary_table_context(pairs, pair_url=lambda c, s: None)
    assert ctx["n_total"] == 151 and len(ctx["rows"]) == 100
    assert ctx["rows"][0]["copier"] == "s0" and ctx["rows"][0]["extreme"]
    assert not ctx["rows"][5]["extreme"]
    assert P.secondary_table_context([], pair_url=lambda c, s: None) is None


def test_match_strip_run_and_classes():
    key = np.array([1, 1, 1, 1, 1])
    c = np.array([1, 2, 3, 0, 4])
    s = np.array([1, 2, 3, 0, 5])
    strip = P.match_strip(c, s, key)
    assert strip["max_run"] == 2
    cls = [col["c_cls"] for col in strip["columns"]]
    assert cls == ["correct", "cwrong run", "cwrong run", "cblank", "lonely"]
    assert strip["columns"][3]["c_lbl"] == "·"


def test_neighbor_relation():
    assert P.neighbor_relation("A1", "A2", None, None)["kind"] == "neighbor"
    assert P.neighbor_relation("A1", "C1", None, None)["kind"] == "far"
    assert P.neighbor_relation("A1", "A1", None, None)["kind"] == "same-seat"
    assert P.neighbor_relation("A1", "A2", "S1", "S2")["kind"] == "other-hall"
    assert P.neighbor_relation("", "A2", None, None)["kind"] == "missing"


def test_term_label_and_sort():
    assert P.term_label("2025-2026", "guz") == "2025-2026 / Güz"
    assert P.term_label("", "") == "Belirtilmemiş"
    terms = ["2024-2025 / Bahar", "2025-2026 / Güz", "2025-2026 / Bahar", "Belirtilmemiş"]
    assert sorted(terms, key=P.term_sort_key)[:3] == [
        "2025-2026 / Bahar", "2025-2026 / Güz", "2024-2025 / Bahar"]


def test_seating_context():
    assert P.seating_context(None) is None
    off = P.seating_context({"filter_active": False, "reason": "kapsam düşük"})
    assert off == {"active": False, "reason": "kapsam düşük"}
    on = P.seating_context({"filter_active": True, "coverage_ratio": 0.9, "n_with_seat": 9,
                            "n_total": 10, "n_halls": 1,
                            "seat_collisions": [["a", "b", "A1"]], "n_parse_errors": 0})
    assert on["coverage_pct"] == "90" and on["n_collisions"] == 1 and "a↔b @ A1" in on["collision_detail"]
