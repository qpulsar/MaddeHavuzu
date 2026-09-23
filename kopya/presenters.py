"""
Kopya Analizi sunum mantığı
===========================
Kaynak (cheating/routes.py) HTML'i f-string'lerle üretiyordu. Burada
biçimlendirme, sıralama, top-N ve şans referansı hesapları düz Python
fonksiyonlarıdır; şablonlar yalnızca hazır sözlükleri basar (autoescape açık).
"""

from __future__ import annotations

import math
from collections import defaultdict
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

import numpy as np

# ── Sabitler ──────────────────────────────────────────────────────────────

PROB_INDEX_ORDER = ("K", "K_star", "K1", "K2", "S1", "S2")
PROB_INDEX_LABELS = {
    "K": "K", "K_star": "K*", "K1": "K1", "K2": "K2",
    "S1": "S1", "S2": "S2",
}
# Top-N sıralamasına giren karar katmanı indeksleri (K empirical hariç)
TOP_INDEX_ORDER = ("K_star", "K1", "K2", "S1", "S2")
# İkincil tablo sıralama anahtarı önceliği
SECONDARY_KEY_ORDER = ("K1", "S1", "K_star", "K2", "S2")

TOP_N_DEFAULT = 10
TOP_N_MIN, TOP_N_MAX = 1, 50
TOP_N_CHOICES = (5, 10, 20)
PRIMARY_TABLE_LIMIT = 200
SECONDARY_TABLE_LIMIT = 100

DESCRIPTIVE_TOOLTIP = ("descriptive only — küçük emsal grubunda alpha "
                       "kontrolü sağlanamaz")

_SEMESTER_TR = {"guz": "Güz", "güz": "Güz", "bahar": "Bahar", "yaz": "Yaz",
                "gz": "Güz", "bh": "Bahar"}

PairUrlFn = Callable[[str, str], Optional[str]]


# ── Sorgu parametreleri ───────────────────────────────────────────────────

def parse_alpha(raw: Any, default: float = 0.01) -> float:
    """alpha sorgu parametresi; geçersiz veya (0, 1) dışıysa varsayılan."""
    try:
        v = float(raw)
    except (TypeError, ValueError):
        return default
    if not (0.0 < v < 1.0) or math.isnan(v):
        return default
    return v


def parse_top_n(raw: Any, default: int = TOP_N_DEFAULT) -> int:
    """top_n sorgu parametresi; 1..50 aralığına kısılır."""
    try:
        v = int(raw)
    except (TypeError, ValueError):
        v = default
    return max(TOP_N_MIN, min(TOP_N_MAX, v))


def fmt_alpha(alpha: float) -> str:
    return f"{alpha:g}"


# ── p-değeri hücresi ──────────────────────────────────────────────────────

def fmt_p(iv, alpha: float) -> Dict[str, str]:
    """IndexValue → {"text", "cls", "title"}.

    Ham p (p_raw) gösterilir. Kırmızı ("hit") BH-FDR düzeltilmiş p_adj ≤ α ise.
    Tooltip'te p_adj. DESCRIPTIVE_ONLY: gri italik, kırmızı yok.
    NOT_COMPUTABLE / yok: "-".
    """
    if iv is None or iv.status == "NOT_COMPUTABLE":
        return {"text": "-", "cls": "na", "title": ""}
    p_adj = iv.p_adjusted
    val = iv.p_raw if iv.p_raw is not None else 0.0
    if iv.status == "DESCRIPTIVE_ONLY":
        return {"text": f"{val:.4f}", "cls": "na", "title": DESCRIPTIVE_TOOLTIP}
    cls = "hit" if (p_adj is not None and p_adj <= alpha) else ""
    title = (f"p_adj (BH-FDR) = {p_adj:.4f}" if p_adj is not None
             else "p_adj: hesaplanmadı")
    return {"text": f"{val:.4f}", "cls": cls, "title": title}


def hit_count(iv_list: Iterable, alpha: float) -> int:
    """Karar katmanı indeksleri için p_adj ≤ α sayımı.
    DESCRIPTIVE_ONLY / NOT_COMPUTABLE sayılmaz."""
    n = 0
    for iv in iv_list:
        if iv is None:
            continue
        if iv.status in ("NOT_COMPUTABLE", "DESCRIPTIVE_ONLY"):
            continue
        p = iv.p_adjusted if iv.p_adjusted is not None else iv.p_raw
        if p is not None and p <= alpha:
            n += 1
    return n


# ── Liste sayfası yardımcıları ────────────────────────────────────────────

def term_label(academic_year: str, semester: str) -> str:
    """Örn. "2025-2026 / Güz"; bilinmiyorsa "Belirtilmemiş"."""
    y = (academic_year or "").strip()
    s = (semester or "").strip()
    if not y and not s:
        return "Belirtilmemiş"
    s_disp = _SEMESTER_TR.get(s.lower(), s.capitalize() if s else "?")
    return (f"{y} / {s_disp}" if y and s else (y or s_disp)) or "Belirtilmemiş"


def term_sort_key(term: str):
    """Yıl/dönem başlıkları: en yeni önce (Bahar=2 > Güz=1 > Yaz=0)."""
    y_score = 0
    try:
        year_part = term.split(" / ")[0]
        if "-" in year_part:
            y_score = int(year_part.split("-")[-1])
        elif year_part.isdigit():
            y_score = int(year_part)
    except (ValueError, IndexError):
        pass
    d_score = 0
    if "Bahar" in term:
        d_score = 2
    elif "Güz" in term:
        d_score = 1
    return (-y_score, -d_score, term)


def short_date(iso: str) -> str:
    """ISO tarih → 'YYYY-MM-DD HH:MM'."""
    if not iso:
        return "-"
    d = str(iso).split("+")[0].split("Z")[0]
    return d.replace("T", " ")[:16]


# ── Panel bölümleri ───────────────────────────────────────────────────────

def seating_context(sr: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Oturma verisi özeti + veri kalitesi uyarıları (None: bölüm yok)."""
    if not sr:
        return None
    if not sr.get("filter_active"):
        return {"active": False, "reason": sr.get("reason") or "-"}
    collisions = sr.get("seat_collisions", []) or []
    n_perr = int(sr.get("n_parse_errors", 0) or 0)
    return {
        "active": True,
        "coverage_pct": f"{float(sr.get('coverage_ratio', 0.0)) * 100:.0f}",
        "n_with_seat": sr.get("n_with_seat"),
        "n_total": sr.get("n_total"),
        "n_halls": sr.get("n_halls") or "?",
        "n_collisions": len(collisions),
        "collision_detail": "; ".join(
            f"{c[0]}↔{c[1]} @ {c[2]}" for c in collisions[:3] if len(c) >= 3),
        "n_parse_errors": n_perr,
        "parse_error_detail": "; ".join(
            str(x) for x in (sr.get("parse_error_examples") or [])[:3]),
    }


def split_tiers(pairs) -> Tuple[list, list]:
    primary = [pr for pr in pairs if pr.tier == "primary"]
    secondary = [pr for pr in pairs if pr.tier == "secondary"]
    return primary, secondary


def count_couples(pairs) -> int:
    """Yönsüz öğrenci ikilisi sayısı (BH-FDR test sayısı; SIM-17)."""
    return len({frozenset({pr.copier_id, pr.source_id}) for pr in pairs})


def is_fdr_hit(pr, alpha: float) -> bool:
    for name in TOP_INDEX_ORDER:
        iv = pr.indices.get(name)
        if iv is not None and iv.p_adjusted is not None and iv.p_adjusted <= alpha:
            return True
    return False


def rank_top_suspicious(primary_pairs, top_n: int) -> List[Tuple[float, str, Any]]:
    """Yön ikilisi bazlı sıralama: her ikili için iki yönün 5 indeksindeki
    minimum ham p (p_raw). Döner: [(min_p, indeks_adı, çift), ...] ilk top_n."""
    couples: Dict[Any, List] = defaultdict(list)
    for pr in primary_pairs:
        couples[frozenset({pr.copier_id, pr.source_id})].append(pr)
    scored: List[Tuple[float, str, Any]] = []
    for pair_list in couples.values():
        best = None
        for pr in pair_list:
            for name in TOP_INDEX_ORDER:
                iv = pr.indices.get(name)
                if iv is None or iv.p_raw is None:
                    continue
                if best is None or float(iv.p_raw) < best[0]:
                    best = (float(iv.p_raw), name, pr)
        if best is not None:
            scored.append(best)
    scored.sort(key=lambda x: x[0])
    return scored[:top_n]


def chance_reference(observed_min: Optional[float],
                     m_couples: int) -> Optional[Dict[str, Any]]:
    """Şans referansı: hiç kopya olmayan sınıfta m karşılaştırmada beklenen
    en düşük p ≈ 1/(m+1). Yorum metni parçalara ayrılır
    (lead + <b>bold</b> + tail) — şablon |safe kullanmadan kalın basar."""
    if m_couples <= 0 or observed_min is None:
        return None
    expected_min = 1.0 / (m_couples + 1)
    ratio = observed_min / expected_min if expected_min > 0 else 0.0
    if ratio < 0.5:
        tone = "strong"
        lead, bold, tail = ("gözlenen değer beklentinin ",
                            f"{ratio:.2f}× altında", " — belirgin sinyal olabilir")
    elif ratio < 1.0:
        tone = "weak"
        lead, bold, tail = ("gözlenen değer beklentinin ",
                            f"{ratio:.2f}× altında",
                            " — küçük fark, belirgin sinyal değil")
    elif ratio < 2.0:
        tone = "neutral"
        lead, bold, tail = (f"gözlenen değer beklentiyle uyumlu ({ratio:.2f}×) — "
                            f"tesadüfle açıklanabilir", "", "")
    else:
        tone = "neutral"
        lead, bold, tail = ("gözlenen beklentiden yüksek — sıradan davranış", "", "")
    return {
        "observed": f"{observed_min:.4f}",
        "expected": f"{expected_min:.4f}",
        "m": m_couples,
        "ratio": ratio,
        "tone": tone,
        "interp_lead": lead,
        "interp_bold": bold,
        "interp_tail": tail,
    }


def top_suspicious_context(primary_pairs, top_n: int, m_couples: int,
                           alpha: float, pair_url: PairUrlFn,
                           top_n_url: Callable[[int], str]) -> Optional[Dict[str, Any]]:
    """En şüpheli N çift paneli (SIM-18 hibrit c). Karar aracı değildir."""
    if not primary_pairs:
        return None
    top = rank_top_suspicious(primary_pairs, top_n)
    rows = []
    for min_p, driving, pr in top:
        rows.append({
            "copier": pr.copier_id,
            "source": pr.source_id,
            "min_p": f"{min_p:.4f}",
            "driving": driving,
            "fdr_hit": is_fdr_hit(pr, alpha),
            "common_wrong": int(pr.descriptive.get("common_wrong", 0)),
            "url": pair_url(pr.copier_id, pr.source_id),
        })
    observed_min = top[0][0] if top else None
    return {
        "top_n": top_n,
        "m_couples": m_couples,
        "buttons": [{"n": n, "active": n == top_n, "url": top_n_url(n)}
                    for n in TOP_N_CHOICES],
        "rows": rows,
        "chance": chance_reference(observed_min, m_couples),
    }


def primary_table_context(primary_pairs, alpha: float, n_couples: int,
                          pair_url: PairUrlFn) -> Dict[str, Any]:
    """Birincil katman: gösterge sayısına göre azalan, ilk 200 satır."""
    scored = []
    for pr in primary_pairs:
        flags = hit_count([pr.indices.get(k) for k in PROB_INDEX_ORDER], alpha)
        scored.append((flags, pr))
    scored.sort(key=lambda x: (-x[0], x[1].copier_id, x[1].source_id))
    rows = []
    for flags, pr in scored[:PRIMARY_TABLE_LIMIT]:
        rows.append({
            "copier": pr.copier_id,
            "source": pr.source_id,
            "is_neighbor": pr.is_neighbor is True,
            "common_wrong": int(pr.descriptive.get("common_wrong", 0)),
            "cells": [fmt_p(pr.indices.get(k), alpha) for k in PROB_INDEX_ORDER],
            "flags": flags,
            "url": pair_url(pr.copier_id, pr.source_id),
        })
    return {
        "headers": [PROB_INDEX_LABELS[k] for k in PROB_INDEX_ORDER],
        "rows": rows,
        "n_total": len(scored),
        "n_couples": n_couples,
        "limit": PRIMARY_TABLE_LIMIT,
    }


def secondary_sort_p(pr) -> float:
    """Sıralama anahtarı — K1 p_raw (yoksa S1, K_star, K2, S2; hiçbiri yoksa 1.0)."""
    for name in SECONDARY_KEY_ORDER:
        iv = pr.indices.get(name)
        if iv is not None and iv.p_raw is not None:
            return float(iv.p_raw)
    return 1.0


def secondary_table_context(secondary_pairs,
                            pair_url: PairUrlFn) -> Optional[Dict[str, Any]]:
    """İkincil katman (komşuluk dışı): K1 p_raw artan, ilk 100; karar yok."""
    if not secondary_pairs:
        return None
    ordered = sorted(secondary_pairs,
                     key=lambda pr: (secondary_sort_p(pr), pr.copier_id, pr.source_id))
    n = len(ordered)
    threshold_p = None
    if n >= 100:
        top1_idx = max(1, n // 100)
        threshold_p = secondary_sort_p(ordered[top1_idx - 1])
    rows = []
    for pr in ordered[:SECONDARY_TABLE_LIMIT]:
        d = pr.descriptive
        p_val = secondary_sort_p(pr)
        rows.append({
            "copier": pr.copier_id,
            "source": pr.source_id,
            "extreme": threshold_p is not None and p_val <= threshold_p and p_val < 1.0,
            "p_disp": f"{p_val:.4f}" if p_val < 1.0 else "—",
            "common_wrong": int(d.get("common_wrong", 0)),
            "common_blank": int(d.get("common_blank", 0)),
            "run": int(d.get("longest_common_wrong_run", 0)),
            "url": pair_url(pr.copier_id, pr.source_id),
        })
    return {"rows": rows, "n_total": n, "limit": SECONDARY_TABLE_LIMIT}


def dashboard_context(source_id: str, meta: Dict[str, Any], result, alpha: float,
                      top_n: int, sensitivity_message: str,
                      pair_url: PairUrlFn,
                      top_n_url: Callable[[int], str]) -> Dict[str, Any]:
    primary, secondary = split_tiers(result.pairs)
    m_couples = count_couples(primary)
    return {
        "source_id": source_id,
        "alpha": alpha,
        "alpha_disp": fmt_alpha(alpha),
        "warnings": list(meta.get("warnings") or []),
        "course_code": meta.get("course_code", ""),
        "course_name": meta.get("course_name", ""),
        "exam_type": meta.get("exam_type", ""),
        "module_version": result.module_version,
        "computed_at": result.computed_at,
        "stats": {
            "n_valid": result.n_valid,
            "n_items": meta.get("n_items", 0),
            "n_booklets": len(meta.get("booklets", []) or []),
            "n_pairs": len(result.pairs),
        },
        "sensitivity_message": sensitivity_message,
        "seating": seating_context(result.seating_report),
        "top": top_suspicious_context(primary, top_n, m_couples, alpha,
                                      pair_url, top_n_url),
        "primary": primary_table_context(primary, alpha, m_couples, pair_url),
        "secondary": secondary_table_context(secondary, pair_url),
    }


# ── Çift detayı ───────────────────────────────────────────────────────────

_LETTER = {1: "A", 2: "B", 3: "C", 4: "D", 5: "E", 6: "F"}


def answer_label(v: int) -> str:
    if v == 0:
        return "·"
    if v == -1:
        return "×"
    return _LETTER.get(int(v), str(int(v)))


def find_pair(result, copier: str, source: str):
    for pr in result.pairs:
        if pr.copier_id == copier and pr.source_id == source:
            return pr
    return None


def longest_common_wrong_run(resp_c, resp_s, key) -> Tuple[int, int, int]:
    """(uzunluk, başlangıç, bitiş) — ortak yanlış ardışık en uzun blok."""
    max_run, cur, run_end = 0, 0, -1
    for i in range(len(key)):
        vc, vs, k = int(resp_c[i]), int(resp_s[i]), int(key[i])
        if vc >= 1 and vs >= 1 and vc == vs and vc != k:
            cur += 1
            if cur > max_run:
                max_run = cur
                run_end = i
        else:
            cur = 0
    run_start = run_end - max_run + 1 if max_run > 0 else -1
    return max_run, run_start, run_end


def _cell_class(v_self: int, v_other: int, k: int, in_run: bool) -> str:
    if v_self == 0:
        return "cblank"
    if v_self == k:
        return "correct"
    if v_self == v_other:
        return "cwrong run" if in_run else "cwrong"
    return "lonely"


def match_strip(resp_c, resp_s, key) -> Dict[str, Any]:
    """Madde eşleşme haritası: sütun başına anahtar / şüpheli / kaynak hücresi."""
    max_run, run_start, run_end = longest_common_wrong_run(resp_c, resp_s, key)
    columns = []
    for i in range(len(key)):
        vc, vs, k = int(resp_c[i]), int(resp_s[i]), int(key[i])
        in_run = max_run >= 2 and run_start <= i <= run_end
        columns.append({
            "num": i + 1,
            "key": answer_label(k),
            "c_lbl": answer_label(vc),
            "c_cls": _cell_class(vc, vs, k, in_run),
            "s_lbl": answer_label(vs),
            "s_cls": _cell_class(vs, vc, k, in_run),
        })
    return {"columns": columns, "max_run": max_run}


def index_rows(pr, alpha: float) -> List[Dict[str, Any]]:
    rows = []
    for name in PROB_INDEX_ORDER:
        iv = pr.indices.get(name)
        if iv is None:
            continue
        if iv.status == "NOT_COMPUTABLE":
            rows.append({"label": PROB_INDEX_LABELS[name], "computable": False,
                         "reason": iv.reason or ""})
            continue
        rows.append({
            "label": PROB_INDEX_LABELS[name],
            "computable": True,
            "value": f"{iv.value:.5f}" if iv.value is not None else "-",
            "p_raw": f"{iv.p_raw:.5f}" if iv.p_raw is not None else "-",
            "p_adj": f"{iv.p_adjusted:.5f}" if iv.p_adjusted is not None else "-",
            "hit": iv.p_adjusted is not None and iv.p_adjusted <= alpha,
        })
    return rows


def _clean_hall(hall, i) -> Optional[str]:
    if hall is None or hall[i] is None or not str(hall[i]).strip():
        return None
    return str(hall[i])


def neighbor_relation(seat_c: str, seat_s: str,
                      hall_c: Optional[str], hall_s: Optional[str]) -> Dict[str, str]:
    """Oturma ilişkisi (SIM-13): komşu mu, değilse aradaki mesafe."""
    from kopya.engine._neighbor import parse_seat_label
    p_c = parse_seat_label(seat_c) if seat_c else None
    p_s = parse_seat_label(seat_s) if seat_s else None
    if not (p_c and p_s):
        return {"kind": "missing", "text": "— oturma kodu eksik"}
    same_hall = (hall_c == hall_s) if (hall_c and hall_s) else True
    dr = abs(p_c[0] - p_s[0])
    dc = abs(p_c[1] - p_s[1])
    if not same_hall:
        return {"kind": "other-hall", "text": "farklı salon (komşu değil)"}
    if (dr, dc) == (0, 0):
        return {"kind": "same-seat", "text": "aynı koltuk (veri hatası)"}
    if dr <= 1 and dc <= 1:
        return {"kind": "neighbor", "text": f"komşu (Moore, Δsatır={dr}, Δkoltuk={dc})"}
    return {"kind": "far", "text": f"komşu değil (Δsatır={dr}, Δkoltuk={dc})"}


def person_fit_value(result, name: str, student: str) -> Optional[float]:
    """Kişi-uyum değeri. person_fit dizileri yalnız analize giren (dışlanmamış)
    öğrencileri kapsar ve `result.student_id` sırasındadır — tam öğrenci
    listesindeki indeksle değil, oradaki konumla aranmalıdır."""
    arr = (result.person_fit or {}).get(name)
    if arr is None:
        return None
    for i, sid in enumerate(result.student_id):
        if str(sid) == student:
            if i >= len(arr):
                return None
            v = float(arr[i])
            return None if math.isnan(v) else v
    return None


def fmt3(x: Optional[float]) -> str:
    if x is None:
        return "-"
    try:
        if x != x:
            return "-"
        return f"{x:.3f}"
    except (TypeError, ValueError):
        return "-"


def pair_context(data, result, copier: str, source: str,
                 alpha: float) -> Dict[str, Any]:
    """Çift detay sayfası bağlamı. Çift/öğrenci bulunamazsa {"error": ...}."""
    from kopya.engine.core import to_canonical_matrix

    pr = find_pair(result, copier, source)
    if pr is None:
        return {"error": f"Çift bulunamadı: {copier} → {source}"}

    canonical = to_canonical_matrix(data.responses, data.booklet, data.permutation)
    idx_of = {str(sid): i for i, sid in enumerate(data.student_id)}
    ci = idx_of.get(copier)
    si = idx_of.get(source)
    if ci is None or si is None:
        return {"error": "Öğrenci kanonik matrise girmemiş."}

    key = np.asarray(data.key)
    strip = match_strip(canonical[ci], canonical[si], key)

    seat_c = str(data.seat_code[ci] or "") if data.seat_code is not None else ""
    seat_s = str(data.seat_code[si] or "") if data.seat_code is not None else ""
    neighbor = neighbor_relation(seat_c, seat_s,
                                 _clean_hall(data.hall, ci), _clean_hall(data.hall, si))

    d = pr.descriptive
    return {
        "error": None,
        "copier": copier,
        "source": source,
        "alpha_disp": fmt_alpha(alpha),
        "module_version": result.module_version,
        "strip": strip,
        "index_rows": index_rows(pr, alpha),
        "tiles": [
            {"label": "Ortak Yanlış", "value": int(d.get("common_wrong", 0))},
            {"label": "Ortak Doğru", "value": int(d.get("common_correct", 0))},
            {"label": "Ortak Boş", "value": int(d.get("common_blank", 0))},
            {"label": "Uyum Oranı", "value": f"{float(d.get('agreement_rate', 0)):.2f}"},
            {"label": "En Uzun Blok", "value": strip["max_run"]},
        ],
        "same_booklet": "Aynı" if pr.same_booklet else "Farklı",
        "seat_c": seat_c or "—",
        "seat_s": seat_s or "—",
        "neighbor": neighbor,
        "u3_c": fmt3(person_fit_value(result, "U3", copier)),
        "u3_s": fmt3(person_fit_value(result, "U3", source)),
        "ht_c": fmt3(person_fit_value(result, "HT", copier)),
        "ht_s": fmt3(person_fit_value(result, "HT", source)),
    }
