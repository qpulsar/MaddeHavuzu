"""
Cheating — Cift Duzeyi Orkestrasyon
====================================
Bir sinav icin tum (yonlu) ogrenci ciftleri uzerinde K/K*/K1/K2/S1/S2
indekslerini hesaplar; kisi-bazli U3 ve H^T'yi populasyon icin bir kez
uretir. Benjamini-Hochberg FDR ile coklu-karsilastirma duzeltmesi
uygular. n-kapisi ile ne kadar guvenilir gosterge uretileceğini
etiketler.

Yönlülük
--------
Her (i, j) yönlü cift bir kez hesaplanir; (i, j) copier=i, source=j.
i != j; excluded=True kisiler tamamen dislanir.

n-kapisi (2026-09-09 KALDIRILDI)
--------------------------------
Eski spec §5.1 eşikleri (INSUFFICIENT<40, WEAK_EVIDENCE 40-99, OK≥100)
**ampirik dayanaktan yoksun** çıktı. Simülasyon (`cheating/simulation/`,
36 hücre × 1000 rep) tespit:
  - n=20 K1 gücü (k=40, pct=.40): 0.454 (n=200'de 0.542; fark %17)
  - I. tip hata her n'de nominal α altında; n=20'de daha da muhafazakâr
  - Küçük n'de yeni NC modu yok; NC hâlâ w_s=0 kaynaklı (~%6)
Bkz. `cheating/simulation/FINDINGS.md` §0.

**Yeni davranış**: n eşiği yok. İndeksler her n'de hesaplanır. Karar
sebebe dayalı çift-düzeyi kontrolle verilir:
  - w_s = 0 → NOT_COMPUTABLE (anlaşılır sebep metniyle)
  - GLM yakınsamama → NOT_COMPUTABLE
  - G² kapısı kapalı (S1/S2, p<.01) → NOT_COMPUTABLE
Duyarlılık göstergesi (bağlamsal güç kestirimi) UI'da ayrıca gösterilir.
Geriye uyum: `AnalysisResult.n_gate` alanı korundu, hep "OK" döner.

FDR
---
Her indeks icin AYRI Benjamini-Hochberg step-up. p_raw asla None ise
dahil edilmez. p_adjusted IndexValue.p_adjusted alanina yazilir.

Cikti
-----
AnalysisResult(dataclass): pairs listesi + populasyon-bazli person-fit
skorlar + meta (alpha, correction, n_valid, n_gate, module_version).
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

import numpy as np

from kopya.engine.core import (
    ExamData,
    IndexValue,
    PairResult,
    to_canonical_matrix,
    validate_exam_data,
)
from kopya.engine._descriptive import descriptive_pair
from kopya.engine._formulas import (
    G2_ALPHA,
    K_empirical,
    K_star,
    K1,
    K2,
    S1,
    S2,
    SubgroupExclusion,
)
from kopya.engine._person_fit import U3, HT, to_binary_matrix


NGate = Literal["INSUFFICIENT", "WEAK_EVIDENCE", "OK"]

# S2/S1 icin belirsizlik durumlari: reason -> status mapping
_REASON_NOT_COMPUTABLE = "NOT_COMPUTABLE"


def _n_gate(n: int) -> NGate:
    """DEPRECATED — n eşiği kaldırıldı (2026-09-09).

    Simülasyon (36 hücre × 1000 rep) mevcut eşiklerin ampirik dayanaktan
    yoksun olduğunu gösterdi. Fonksiyon geriye uyum için tutuldu; her n
    için "OK" döner. Karar sebebe dayalı çift-düzeyi kontrolle verilir.
    """
    return "OK"


def bh_fdr(p_values: np.ndarray) -> np.ndarray:
    """Benjamini-Hochberg FDR düzeltmesi (step-up).

    Girdi: p_values (1D array). NaN'lar aynen döndürülür.
    Çıktı: p_adjusted (aynı uzunlukta).

    Formül:
      Sıralı p'ler p_(1) <= ... <= p_(m); rank i (1-based).
      p_adj_(i) = min_{k >= i} (m * p_(k) / k), sonra clip [0, 1].
    """
    p = np.asarray(p_values, dtype=np.float64)
    n = len(p)
    if n == 0:
        return p.copy()

    valid_mask = ~np.isnan(p)
    if not valid_mask.any():
        return p.copy()

    pv = p[valid_mask]
    m = len(pv)
    order = np.argsort(pv)
    ranked = pv[order]
    # Ham BH: p_(i) * m / i
    raw = ranked * m / (np.arange(1, m + 1, dtype=np.float64))
    # Monotonicity: sagdan sola en kucuk
    mono = np.minimum.accumulate(raw[::-1])[::-1]
    mono = np.clip(mono, 0.0, 1.0)

    adj_valid = np.empty(m, dtype=np.float64)
    adj_valid[order] = mono

    out = p.copy()
    out[valid_mask] = adj_valid
    return out


# ── Tek cift icin tum indeksler ───────────────────────────

_INDEX_NAMES_PROB = ("K_star", "K1", "K2", "S1", "S2")  # olasilik + karar katmani
_INDEX_NAMES_DESCRIPTIVE = ("K",)  # hesaplanir ama karar katmaninda degil


def _extract_diagnostics(meta: Any) -> Optional[Dict[str, float]]:
    """S1/S2 meta dict'inden yapisal diagnostiklieri cek (G² dahil)."""
    if not isinstance(meta, dict):
        return None
    keys = ("g2", "g2_df", "g2_p_value", "mu_c", "beta0", "beta1",
             "n_points", "m_cc", "m_star_cc")
    out: Dict[str, float] = {}
    for k in keys:
        if k in meta and meta[k] is not None:
            try:
                out[k] = float(meta[k])
            except (TypeError, ValueError):
                pass
    return out or None


# NC sebep kod → insan-okur metin eşleşmesi (2026-09-09)
_REASON_MESSAGES = {
    "w_s == 0": ("Kaynak öğrencinin yanlış yanıtı yok — "
                  "karşılaştırılacak madde bulunmuyor"),
    "empty c'": ("Şüpheli öğrenciyle aynı yanlış sayısına sahip başka "
                  "öğrenci yok — emsal grubu boş"),
    "< 2 subgroup": ("Alt grup sayısı yetersiz — regresyon "
                       "fit'i için en az 2 farklı yanlış-sayısı grubu gerekli"),
    "copier subgroup bos": ("Şüpheli öğrenciyle aynı yanlış sayısına sahip "
                              "başka öğrenci yok — emsal grubu boş"),
}


def _humanize_reason(raw: Optional[str]) -> Optional[str]:
    """Fonksiyon dahili sebep koduna insan-okur metin eşleşmesi.

    - `w_s == 0` gibi kısa kodları çevirir
    - `poisson GLM: <detay>` bilgisini olduğu gibi bırakır (S1/S2 için)
    - Bilinmeyen kod → kendisi
    """
    if not raw:
        return None
    if raw in _REASON_MESSAGES:
        return _REASON_MESSAGES[raw]
    return raw  # zaten aciklayici bir metin (GLM yakinsamama, G² kapisi, vs.)


def _to_index_value(res_tuple, n_gate: NGate,
                     descriptive_only: bool = False,
                     apply_g2_gate: bool = False) -> IndexValue:
    """(value, meta) -> IndexValue.

    n_gate parametresi geriye-uyum için tutuldu; artık davranışı
    etkilemez (n eşiği 2026-09-09 kaldırıldı).

    descriptive_only=True: status "DESCRIPTIVE_ONLY". Karar katmaninda
    (kirmizi isaretleme, FDR) kullanilmaz. K empirical icin.

    apply_g2_gate=True: S1/S2 icin — G² model uyum p-degeri
    G2_ALPHA (0.01) altinda ise status NOT_COMPUTABLE olur (Sotaridona
    2003 s.10 esik). G² her zaman diagnostics'e yazilir; kapi kapansa
    da deger raporlanir.
    """
    val, meta = res_tuple
    diag = _extract_diagnostics(meta)
    raw_reason = (meta or {}).get("reason") if isinstance(meta, dict) else None
    if val is None:
        return IndexValue(
            value=None, p_raw=None, p_adjusted=None,
            status=_REASON_NOT_COMPUTABLE,
            reason=_humanize_reason(raw_reason),
            diagnostics=diag,
        )
    if descriptive_only:
        return IndexValue(
            value=float(val),
            p_raw=float(val),
            p_adjusted=None,
            status="DESCRIPTIVE_ONLY",
            reason=(
                f"n_c'={meta.get('n_c_prime', '?')}: ayrik dagilimda kucuk "
                f"emsal grubu icin alpha=.01 kontrolu saglanamaz "
                f"(uniformity baseline'a bakiniz)"
            ) if isinstance(meta, dict) else None,
            diagnostics=diag,
        )
    # G² kapisi — sadece S1/S2 icin
    if apply_g2_gate and diag is not None:
        g2_p = diag.get("g2_p_value")
        if g2_p is not None and g2_p < G2_ALPHA:
            g2 = diag.get("g2")
            df = diag.get("g2_df")
            return IndexValue(
                value=float(val),  # deger korunur — rapor amacli
                p_raw=None,        # ama karar katmani (FDR) icin devre disi
                p_adjusted=None,
                status=_REASON_NOT_COMPUTABLE,
                reason=(f"Loglineer modelin uyumu yetersiz "
                        f"(G²={g2:.2f}, df={df:.0f}, p={g2_p:.4g} < "
                        f"{G2_ALPHA}) — S1/S2 kopya testi olarak "
                        f"kullanilamaz (Sotaridona 2003 s.10)"),
                diagnostics=diag,
            )
    # n eşiği kaldırıldı: hep OK
    return IndexValue(
        value=float(val),
        p_raw=float(val),
        p_adjusted=None,
        status="OK",
        reason=None,
        diagnostics=diag,
    )


def _compute_pair(canonical: np.ndarray, key: np.ndarray,
                    copier_idx: int, source_idx: int,
                    num_items: int, n_options: int,
                    n_gate: NGate,
                    student_id: np.ndarray,
                    booklet: np.ndarray,
                    include_prob_indices: bool,
                    subgroup_exclusion: SubgroupExclusion = "source_only",
                    tier: str = "primary",
                    is_neighbor: Optional[bool] = None,
                    ) -> PairResult:
    """Yonlu cift (copier=i, source=j) icin tum indeksleri hesapla.

    subgroup_exclusion K1/K2/S1/S2'e propaganda edilir. K_empirical/K_star
    yayimlanmis tanim geregi c' subgroup'a kendini almiyor — bu mod'un
    disinda.
    """
    c = canonical[copier_idx]
    s = canonical[source_idx]

    # Descriptive her zaman hesaplanir (INSUFFICIENT dahil).
    desc = descriptive_pair(c, s, key)

    indices: Dict[str, IndexValue] = {}
    if include_prob_indices:
        # K empirical descriptive_only: kucuk subgroup'ta ayrik dagilim
        # nedeniyle karar katmaninda kullanilmaz. Bkz. README ve
        # cheating/validation/uniformity_baseline.json
        indices["K"] = _to_index_value(
            K_empirical(canonical, key, copier_idx, source_idx),
            n_gate, descriptive_only=True)
        # K_star icin exclusion modu CopyDetect `k()` referansi ile uyumlu
        # olarak "none". K1/K2/S1/S2 ise "source_only" (yayimlanmis
        # tanim + ks12 referans uyumu). Referansta iki fonksiyon farkli
        # subgroup dislama uyguluyor — S29_REPORT §4.5.
        indices["K_star"] = _to_index_value(
            K_star(canonical, key, copier_idx, source_idx,
                    subgroup_exclusion="none"), n_gate)
        indices["K1"] = _to_index_value(
            K1(canonical, key, copier_idx, source_idx, num_items,
                subgroup_exclusion=subgroup_exclusion), n_gate)
        indices["K2"] = _to_index_value(
            K2(canonical, key, copier_idx, source_idx, num_items,
                subgroup_exclusion=subgroup_exclusion), n_gate)
        indices["S1"] = _to_index_value(
            S1(canonical, key, copier_idx, source_idx,
                subgroup_exclusion=subgroup_exclusion), n_gate,
            apply_g2_gate=True)
        indices["S2"] = _to_index_value(
            S2(canonical, key, copier_idx, source_idx, n_options,
                subgroup_exclusion=subgroup_exclusion), n_gate,
            apply_g2_gate=True)

    return PairResult(
        copier_id=str(student_id[copier_idx]),
        source_id=str(student_id[source_idx]),
        same_booklet=bool(booklet[copier_idx] == booklet[source_idx]),
        indices=indices,
        descriptive=desc,
        n_used=int(canonical.shape[0]),
        tier=tier,
        is_neighbor=is_neighbor,
    )


# ── Sonuc konteyner ───────────────────────────────────────

@dataclass(frozen=True)
class AnalysisResult:
    """Bir sinav analizinin toplam sonucu.

    - pairs: yonlu (copier, source) ciftlerinin PairResult listesi
    - person_fit: {"U3": arr, "HT": arr} her ogrenci icin skor
                   (indeks student_id sirasi ile ayni)
    - student_id: analize giren ogrencilerin id'leri (excluded haric)
    - n_valid: hesaba giren ogrenci sayisi
    - n_gate: INSUFFICIENT / WEAK_EVIDENCE / OK
    - alpha: eşik seçimi (default 0.01)
    - correction: "BH" (Benjamini-Hochberg)
    - subgroup_exclusion: "source_only" | "source_and_copier"
    - module_version: cheating.__version__
    - computed_at: ISO zaman damgasi
    - input_hash: ExamData bileşenlerinin SHA256 kısası (S29 icin)
    """
    pairs: List[PairResult]
    person_fit: Dict[str, np.ndarray]
    student_id: np.ndarray
    n_valid: int
    n_gate: NGate
    alpha: float
    correction: str
    subgroup_exclusion: str
    module_version: str
    computed_at: str
    input_hash: str = ""
    seating_report: Optional[Dict[str, Any]] = None


# ── Ana giris noktasi ─────────────────────────────────────

def _input_hash(data: ExamData) -> str:
    """ExamData'nin SHA256 kısası (16 hex). S29 reproducibility icin."""
    import hashlib
    h = hashlib.sha256()
    for arr in (data.responses, data.key, data.booklet, data.permutation):
        h.update(np.ascontiguousarray(arr).tobytes())
    # student_id (object dtype) icin str hash
    h.update("|".join(str(x) for x in data.student_id).encode("utf-8"))
    h.update(int(data.n_options).to_bytes(4, "little"))
    if data.excluded is not None:
        h.update(np.ascontiguousarray(data.excluded).tobytes())
    return h.hexdigest()[:16]


def analyze_exam(data: ExamData,
                  alpha: float = 0.01,
                  subgroup_exclusion: SubgroupExclusion = "source_only",
                  ) -> AnalysisResult:
    """Sinav duzeyinde kopya analizi yap.

    Parametreler:
        alpha: kirmizi/gosterge esigi (varsayilan 0.01)
        subgroup_exclusion: K1/K2/S1/S2 fit'inde emsal grubundan copier'in
            dislanip dislanmayacagi.
            "source_only" (varsayilan, yayimlanmis Sotaridona-Meijer 2002/2003
                tanimi — sadece source dislanir; S29 R referans karsilastirmasi
                bu modda yapilir).
            "source_and_copier" (alternatif; kucuk emsal grubunda duyarliligi
                korur; makale-di sapmadir).
    """
    from kopya.engine import __version__

    validate_exam_data(data)
    canonical_full = to_canonical_matrix(
        data.responses, data.booklet, data.permutation)
    key = data.key
    n_students_total, n_items = canonical_full.shape

    # excluded filtresi
    if data.excluded is not None:
        keep_mask = ~data.excluded.astype(bool)
    else:
        keep_mask = np.ones(n_students_total, dtype=bool)
    valid_idx = np.where(keep_mask)[0]
    n_valid = int(len(valid_idx))
    n_gate = _n_gate(n_valid)

    canonical = canonical_full[valid_idx]
    booklet_sub = data.booklet[valid_idx]
    student_id_sub = data.student_id[valid_idx]

    binary = to_binary_matrix(canonical, key)
    u3 = U3(binary)
    ht = HT(binary)

    # n eşiği kaldırıldı (2026-09-09) — indeksler her n için hesaplanır.
    # Karar sebebe dayalı çift-düzeyinde verilir (w_s=0, G² kapısı, GLM
    # yakınsamama). Bkz. `cheating/simulation/FINDINGS.md` §0.
    include_prob = True

    # Oturma verisi (SIM-13): iki katmanli sistem. Filtre otomatik devreye
    # girer. Kapsam < %80 → tek katman (mevcut davranis).
    from kopya.engine._neighbor import (
        parse_seat_label, are_moore_neighbors,
        build_seating_report, DEFAULT_COVERAGE_THRESHOLD,
    )
    seat_codes_sub = (data.seat_code[valid_idx]
                       if data.seat_code is not None else None)
    halls_sub = data.hall[valid_idx] if data.hall is not None else None
    seating_report = build_seating_report(
        student_id_sub, seat_codes_sub, halls_sub,
        coverage_threshold=DEFAULT_COVERAGE_THRESHOLD,
    )
    collision_students = set()
    for a, b, _seat in seating_report.seat_collisions:
        collision_students.add(a); collision_students.add(b)
    parsed_seats = None
    hall_vals = None
    if seating_report.filter_active:
        parsed_seats = [parse_seat_label(seat_codes_sub[i])
                        if seat_codes_sub is not None else None
                        for i in range(n_valid)]
        hall_vals = ([str(halls_sub[i]) if (halls_sub is not None
                                              and halls_sub[i] is not None
                                              and str(halls_sub[i]).strip())
                       else None for i in range(n_valid)])

    pairs: List[PairResult] = []
    n = canonical.shape[0]
    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            # Katman kararı
            if not seating_report.filter_active:
                tier = "primary"; is_nb = None
            else:
                sid_i = str(student_id_sub[i])
                sid_j = str(student_id_sub[j])
                if sid_i in collision_students or sid_j in collision_students:
                    tier = "primary"; is_nb = None  # veri hatası → muhafazakâr
                elif (parsed_seats[i] is None or parsed_seats[j] is None):
                    tier = "primary"; is_nb = None  # kısmi kapsam
                else:
                    is_nb = are_moore_neighbors(
                        parsed_seats[i], parsed_seats[j],
                        hall_vals[i], hall_vals[j])
                    tier = "primary" if is_nb else "secondary"
            pr = _compute_pair(
                canonical=canonical, key=key,
                copier_idx=i, source_idx=j,
                num_items=n_items, n_options=data.n_options,
                n_gate=n_gate,
                student_id=student_id_sub,
                booklet=booklet_sub,
                include_prob_indices=include_prob,
                subgroup_exclusion=subgroup_exclusion,
                tier=tier,
                is_neighbor=is_nb,
            )
            pairs.append(pr)

    # FDR yalnız birincil katmanda (secondary'de p-değeri yok)
    if include_prob:
        primary_idx = [k for k, p in enumerate(pairs) if p.tier == "primary"]
        primary_pairs = [pairs[k] for k in primary_idx]
        primary_adj = _apply_fdr(primary_pairs, list(_INDEX_NAMES_PROB))
        # Secondary çiftlerin p_adjusted=None kalır; ayrıca indices'te
        # p_raw da None yapılır (istatistiksel karar iddiası yok)
        _clear_secondary_p(pairs)
        for k, adj_pr in zip(primary_idx, primary_adj):
            pairs[k] = adj_pr

    return AnalysisResult(
        pairs=pairs,
        person_fit={"U3": u3, "HT": ht},
        student_id=student_id_sub,
        n_valid=n_valid,
        n_gate=n_gate,
        alpha=float(alpha),
        correction="BH",
        subgroup_exclusion=str(subgroup_exclusion),
        module_version=__version__,
        computed_at=datetime.utcnow().isoformat(timespec="seconds") + "Z",
        input_hash=_input_hash(data),
        seating_report={
            "n_total": seating_report.n_total,
            "n_with_seat": seating_report.n_with_seat,
            "coverage_ratio": seating_report.coverage_ratio,
            "n_parse_errors": seating_report.n_parse_errors,
            "parse_error_examples": list(seating_report.parse_error_examples),
            "seat_collisions": [list(c) for c in seating_report.seat_collisions],
            "hall_available": seating_report.hall_available,
            "n_halls": seating_report.n_halls,
            "filter_active": seating_report.filter_active,
            "reason": seating_report.reason,
        },
    )


def _clear_secondary_p(pairs: List[PairResult]) -> None:
    """Secondary çiftlerde:
      - p_raw KORUNUR (sıralama için — SIM-18)
      - p_adjusted → None (FDR uygulanmaz)
      - status → 'DESCRIPTIVE_ONLY'
      - reason: karar iddiası yok, sadece sıralama

    Neden p_raw korunur: ham ortak yanlış sayısıyla sıralama yetenekle
    konfound (düşük yetenekli öğrenci çiftleri fake tepe). İndeks p_raw'i
    yetenek-normalize edilmiş sinyal — sıralama için doğru araç. FDR
    uygulanmadığı için çoklu karşılaştırma sorunu yok.
    """
    for k, pr in enumerate(pairs):
        if pr.tier != "secondary":
            continue
        new_indices: Dict[str, IndexValue] = {}
        for name, iv in pr.indices.items():
            new_indices[name] = replace(
                iv,
                # p_raw KORUNUR — sıralama için
                p_adjusted=None,  # FDR yok
                status="DESCRIPTIVE_ONLY",
                reason=("Komşuluk dışı çift — istatistiksel karar "
                         "üretilmedi; p yalnız sıralama için"),
            )
        pairs[k] = replace(pr, indices=new_indices)


def _apply_fdr(pairs: List[PairResult],
                index_names: List[str]) -> List[PairResult]:
    """Her indeks icin ayri BH-FDR uygulanir — **ogrenci ikilisi
    bazinda** (yonlu cift bazinda DEGIL).

    Neden ikili bazi?
    -----------------
    A→B (A kopyacisi, B kaynagi) ve B→A ayni ogrenci ikilisinin iki
    okumasidir; bagimsiz hipotez degildir. Ikisi ayri test sayilirsa BH
    duzeltmesi 2x sikilasir, gereksiz. Her ikili icin iki yonun min
    p_raw'i alinip BH'e TEK test olarak verilir; adj degeri iki yone de
    ayni yazilir.

    Alternatif: yon ici Bonferroni (min p × 2), sonra BH.
    Sectigimiz yol MIN — hafif liberal, ama m yariya iner (5112 → 2556
    72 ogrenci ornegi). Gerekce: ayni ikilinin p'lerin bagimsiz olmasi
    beklenmez (semantic olarak ayni benzerlik olayi); yon ici cift
    sayimin duzeltme yuku "yon secimi zorluğu" seklinde bir kayip
    getirebilir, min bunu esitler.

    Test sayisi ikili sayidir: n(n-1)/2. Kullanici arayuzunde bu deger
    gorunur ("N ikili uzerinden duzeltme").

    Frozen dataclass'lar replace ile yeniden olusturulur.
    """
    if not pairs:
        return pairs

    from collections import defaultdict
    # Ogrenci ikilisi (yonsuz) → yonlu cift indeksleri
    couples: Dict[Any, List[int]] = defaultdict(list)
    for i, pr in enumerate(pairs):
        key = frozenset({pr.copier_id, pr.source_id})
        couples[key].append(i)
    couple_keys = list(couples.keys())
    n_couples = len(couple_keys)

    # Her indeks × ikili icin min p_raw → BH → ikili basi adj
    per_couple_adj: Dict[str, Dict[Any, float]] = {name: {} for name in index_names}
    for name in index_names:
        min_ps = np.full(n_couples, np.nan)
        for ci, key in enumerate(couple_keys):
            best = np.nan
            for idx in couples[key]:
                iv = pairs[idx].indices.get(name)
                if iv is None or iv.p_raw is None:
                    continue
                v = float(iv.p_raw)
                if np.isnan(best) or v < best:
                    best = v
            min_ps[ci] = best
        adj = bh_fdr(min_ps)
        for ci, key in enumerate(couple_keys):
            per_couple_adj[name][key] = adj[ci]

    # Her yonlu cifti guncelle: ikili adj degerini iki yone ayni yaz
    out: List[PairResult] = []
    for pr in pairs:
        key = frozenset({pr.copier_id, pr.source_id})
        new_indices = dict(pr.indices)
        for name in index_names:
            iv = pr.indices.get(name)
            if iv is None:
                continue
            adj_val = per_couple_adj[name].get(key, np.nan)
            if np.isnan(adj_val):
                new_iv = iv  # NOT_COMPUTABLE veya hepsi p_raw None
            else:
                new_iv = replace(iv, p_adjusted=float(adj_val))
            new_indices[name] = new_iv
        out.append(replace(pr, indices=new_indices))
    return out


__all__ = ["AnalysisResult", "analyze_exam", "bh_fdr"]
