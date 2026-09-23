"""
Cheating — Saf Matematik Formul Katmani
=======================================
Holland (1996) ve Sotaridona & Meijer (2002) formulleriyle K-index ailesi.

Kaynaklar
---------
- Sotaridona & Meijer (2002). Statistical Properties of the K-Index for
  Detecting Answer Copying. J. Educational Measurement, 39(2), 115-132.
  cheating/sotaridona2002.pdf, s. 116-119, denklemler (1), (3), (4), (6), (7).

Yon (asimetri)
--------------
Her cift (copier=c, source=s) icin ayri hesaplanir. c ile s yer degistirirse
farkli deger cikar cunku:
- Emsal grubu (c' subgroup): c ile ayni yanlis sayisina sahip diger ogrenciler
- Binomial denemesi sayisi: w_s (source'un yanlis sayisi)
- Match sayimi: c'nin YANLIS yaptigi maddelerde s ile ayni cevap

Sayisal hassasiyet
------------------
- Ust kuyruk icin scipy.stats.binom.sf(k-1, n, p) = P(X >= k) — asla
  1 - cdf() kullanma (kuyrukta cok kucuk p degerlerinde cokecektir).
- Tum toplam ve mean hesaplari np.float64 uzerinde.
"""

from __future__ import annotations

from typing import Dict, List, Literal, Optional, Tuple

import numpy as np
from scipy import stats


SubgroupExclusion = Literal["source_only", "source_and_copier", "none"]


def _resolve_exclude_copier(mode: SubgroupExclusion,
                             copier_idx: int) -> Optional[int]:
    """Alt grup dislama modu:
    - "source_only": kaynak dislanir, copier subgroup'ta kalir (CopyDetect
      ks12 ampirik doğrulama; Sotaridona-Meijer 2002/2003 yayimlanmis tanim).
    - "source_and_copier": kaynak + copier dislanir (arastirma modu).
    - "none": hicbir dislama YOK. K empirical'in CopyDetect'in `k()` fonk
      davranisi (referans icinde tutarsizlik — ks12 kaynagi dislar,
      k() dislamiyor).
    """
    if mode == "source_and_copier":
        return copier_idx
    return None


# ── Temel sayimlar ────────────────────────────────────────

def wrong_indices(response: np.ndarray, key: np.ndarray) -> np.ndarray:
    """Ogrencinin 'wrong' yaptigi madde indeksleri.

    Wrong = gecerli isaret (1..K) AND anahtardan farkli.
    Bos (0) ve coklu (-1) 'wrong' sayilmaz — Holland/Sotaridona metninde
    'wrong answers' cevap veren ama yanlis olanlari kastediyor.

    # AMBIGUOUS: Sotaridona & Meijer (2002) 'wrong' tanimini blank/coklu
    #   dahil edilip edilmedigi acikca yazmiyor. Genel yorum "gecerli
    #   isaret + yanlis". Boslu senaryolar S29 R karsilastirmasinda
    #   sinanacak.
    """
    valid = response >= 1
    return np.where(valid & (response != key))[0]


def num_wrong(response: np.ndarray, key: np.ndarray) -> int:
    """Ogrencinin yanlis sayisi (w_j)."""
    return int(len(wrong_indices(response, key)))


def matching_wrong(a: np.ndarray, b: np.ndarray, key: np.ndarray) -> int:
    """Iki ogrencinin ayni yanlisi verdigi madde sayisi (M).

    Kosul: her iki cevap da gecerli (1..K), ikisi ayni ve anahtardan
    farkli. (Bos/coklu iceren cevaplar dahil edilmez.)
    """
    valid = (a >= 1) & (b >= 1)
    same = (a == b)
    wrong_a = (a != key)
    return int(np.sum(valid & same & wrong_a))


# ── K empirical (Equation 1) ──────────────────────────────

def K_empirical(canonical: np.ndarray, key: np.ndarray,
                 copier_idx: int, source_idx: int,
                 subgroup_exclusion: SubgroupExclusion = "source_only",
                 ) -> Tuple[Optional[float], Dict[str, int]]:
    """K empirical index (Sotaridona-Meijer 2002, Eqn 1).

    subgroup_exclusion:
      "source_only" (default): kaynak + copier haric (Sotaridona 2002 tanim)
      "source_and_copier": ayni (K empirical zaten copier dislar sabit).
      "none": HICBIRI DISLANMIYOR — CopyDetect k() fonksiyonu davranisi.
              Referans icindeki tutarsizlik (ks12 kaynak dislar, k() dislamaz).

    Doner: (K_degeri, meta) — meta {"n_c_prime", "m_cc"}.
    """
    if canonical.ndim != 2:
        raise ValueError("canonical 2D olmali")
    n = canonical.shape[0]
    if not (0 <= copier_idx < n) or not (0 <= source_idx < n):
        raise ValueError("copier/source indeksleri disinda")
    if copier_idx == source_idx:
        raise ValueError("copier == source olamaz")

    c = canonical[copier_idx]
    s = canonical[source_idx]
    m_cc = matching_wrong(c, s, key)

    w_c = num_wrong(c, key)
    # c' subgroup — mode'a gore dislama:
    others = np.arange(n)
    if subgroup_exclusion == "none":
        pass  # hicbir dislama
    else:
        # source_only ve source_and_copier: her ikisi de dislar (K empirical
        # icin K/K1/K2/S1/S2 farkindan farkli — burada default dislama).
        others = others[(others != copier_idx) & (others != source_idx)]
    if len(others) == 0:
        return None, {"n_c_prime": 0, "m_cc": m_cc}

    subgroup: List[int] = []
    subgroup_ms: List[int] = []
    for j in others:
        if num_wrong(canonical[j], key) == w_c:
            subgroup.append(int(j))
            subgroup_ms.append(matching_wrong(canonical[j], s, key))
    n_c_prime = len(subgroup)
    if n_c_prime == 0:
        return None, {"n_c_prime": 0, "m_cc": m_cc}

    ms_arr = np.array(subgroup_ms, dtype=np.int64)
    z = np.sum(ms_arr >= m_cc)
    K = float(z / n_c_prime)
    return K, {"n_c_prime": n_c_prime, "m_cc": m_cc}


# ── K* — binomial approximation (Equation 4) ──────────────

def _binomial_upper_tail(m: int, n: int, p: float) -> float:
    """P(X >= m) with X ~ Binomial(n, p). scipy sf ile kuyruk-guvenli.

    Sinir durumlari:
    - n == 0 -> P(X >= m) = 1 if m <= 0 else 0
    - p ≤ 0 -> 1 if m <= 0 else 0
    - p ≥ 1 -> 1 if m <= n else 0
    - m <= 0 -> her zaman 1
    """
    if m <= 0:
        return 1.0
    if n <= 0:
        return 0.0
    if p <= 0.0:
        return 0.0
    if p >= 1.0:
        return 1.0 if m <= n else 0.0
    # sf(k) = P(X > k) = P(X >= k+1). Bize P(X >= m) lazim -> sf(m-1).
    return float(stats.binom.sf(m - 1, n, p))


def K_star(canonical: np.ndarray, key: np.ndarray,
            copier_idx: int, source_idx: int,
            subgroup_exclusion: SubgroupExclusion = "none",
            ) -> Tuple[Optional[float], Dict[str, float]]:
    """K* index (Sotaridona-Meijer 2002, Eqn 4).

    p*_c' = m̄_c' / w_s   (subgroup c'nun empirical ortalamasi / w_s)
    K* = P(M >= m_cc), M ~ Binomial(w_s, p*_c')

    Parametreler:
        subgroup_exclusion:
            "none" (varsayilan) — hicbir dislama. CopyDetect `k()`
                fonksiyonu bu modu kullanir; R `K.index` ile birebir
                (S29-K.index dogrulamasi, max|d|=1.7e-16). Referansta
                `ks12()` (K1/K2/S1/S2) kaynagi dislarken `k()` dislamaz —
                referansin kendi ic tutarsizligi (S29_REPORT §4.5). K_star
                icin CopyDetect `k()` mantigini takip etmek uretim
                referansi olarak dogru davranistir.
            "source_only" — Sotaridona-Meijer 2003 yayimlanmis tanimi
                (K1/K2/S1/S2 default'u ile ayni).
            "source_and_copier" — ek muhafazakarlik; K_star icin eski
                Python default'u (S29 oncesi).

    wc == ws durumunda subgroup'a kaynak dusuyorsa "none" modunda kaynagin
    kendi cevabi kendisiyle tam eslesir (m=w_s) → p*_c' sisirir. Bu tam
    olarak CopyDetect referans davranisi.

    Doner: (K*_degeri, meta{'p_star','w_s','m_cc','n_c_prime',...})
    Emsal grubu bossa veya w_s == 0 ise None.
    """
    n = canonical.shape[0]
    if copier_idx == source_idx:
        raise ValueError("copier == source olamaz")

    c = canonical[copier_idx]
    s = canonical[source_idx]
    w_s = num_wrong(s, key)
    m_cc = matching_wrong(c, s, key)

    if w_s == 0:
        return None, {"reason": "w_s == 0", "w_s": 0, "m_cc": m_cc}

    w_c = num_wrong(c, key)
    others = np.arange(n)
    if subgroup_exclusion == "source_and_copier":
        others = others[(others != copier_idx) & (others != source_idx)]
    elif subgroup_exclusion == "source_only":
        others = others[others != source_idx]
    # "none": hicbir dislama
    subgroup_ms = [matching_wrong(canonical[j], s, key)
                    for j in others if num_wrong(canonical[j], key) == w_c]
    n_c_prime = len(subgroup_ms)
    if n_c_prime == 0:
        return None, {"reason": "empty c'", "n_c_prime": 0, "m_cc": m_cc}

    m_bar = float(np.mean(subgroup_ms))
    p_star = m_bar / w_s
    # p_star teorik olarak [0, 1] araliginda; guvenlik icin clamp.
    p_star_clamped = float(min(1.0, max(0.0, p_star)))
    K = _binomial_upper_tail(m_cc, w_s, p_star_clamped)
    return K, {
        "p_star": p_star_clamped,
        "p_star_raw": p_star,
        "w_s": w_s,
        "m_cc": m_cc,
        "n_c_prime": n_c_prime,
        "subgroup_exclusion": subgroup_exclusion,
    }


# ── K1 / K2 — regression tabanli (Eqn 6, 7) ───────────────

def _subgroup_points(canonical: np.ndarray, key: np.ndarray,
                      source_idx: int, num_items: int,
                      copier_idx: Optional[int] = None
                      ) -> Tuple[np.ndarray, np.ndarray, Dict[int, float]]:
    """Her w_r subgroup icin (Q_r, p*_r) noktalarini ve p*_r -> w_r haritasi.

    Q_r = w_r / I (yanlis orani, I: total madde)
    p*_r = m̄_r / w_s

    Source subgroup uyeliginden cikarilir. copier_idx verildiyse copier da
    cikarilir. w_r == 0 subgroup atlanir (p*_r tanimsiz).

    # AMBIGUOUS: Sotaridona-Meijer (2002) makalesi Q_r'yi "proportion of
    #   wrong answers of subgroup r" olarak tanimliyor (s. 116, alt).
    #   Regression sadece p*_r > 0 olan subgroup'lar uzerinde mi yapilir
    #   yoksa hepsi mi — makale acik degil. Figure 1 tumunu cizmis;
    #   ben hepsini dahil ediyorum.
    # AMBIGUOUS: Makale (s. 8) "s does not belong to any number incorrect
    #   group" der. Copier'in subgroup'a dahil olup olmadigi acik degil.
    #   Ancak fit'te copier bulunursa (ozellikle kucuk subgroup'ta) kendi
    #   m'sini yukari ceker ve sensitivity kaybolur. Ben copier'i da hariç
    #   tutuyorum (K empirical / K* zaten oyle yapiyor); tutarli oldu.
    """
    n = canonical.shape[0]
    s = canonical[source_idx]
    w_s = num_wrong(s, key)
    if w_s == 0:
        return np.array([]), np.array([]), {}

    all_wrongs = np.array([num_wrong(canonical[j], key) for j in range(n)])
    unique_ws = np.unique(all_wrongs)

    qs: List[float] = []
    ps: List[float] = []
    w_to_phat_key: Dict[int, float] = {}

    # NOT: R CopyDetect w=0 subgroup'unu dahil eder (p_r = 0 sabit).
    # Regresyon fit'i icin bir sifir noktasi cok bilgilendirici — kalibrasyon
    # (S29) bu detayda R'den ayrisiyordu (Katman 5 K1/K2 farki 3-6e-4).
    # Sabitlendi.
    for w in unique_ws:
        idx = np.where(all_wrongs == w)[0]
        mask = idx != source_idx
        if copier_idx is not None:
            mask = mask & (idx != copier_idx)
        idx = idx[mask]
        if len(idx) == 0:
            continue
        if w == 0:
            # Herkes tam dogru → matching_wrong = 0 → p_r = 0.
            p_r = 0.0
        else:
            ms = np.array([matching_wrong(canonical[j], s, key) for j in idx],
                           dtype=np.float64)
            p_r = float(ms.mean() / w_s)
        q_r = float(w / num_items)
        qs.append(q_r)
        ps.append(p_r)
        w_to_phat_key[int(w)] = p_r

    return np.array(qs, dtype=np.float64), np.array(ps, dtype=np.float64), w_to_phat_key


def _fit_linear(qs: np.ndarray, ps: np.ndarray) -> Optional[np.ndarray]:
    """OLS lineer fit: p = b0 + b1*q. En az 2 nokta gerek."""
    if len(qs) < 2:
        return None
    A = np.column_stack([np.ones_like(qs), qs])
    coef, *_ = np.linalg.lstsq(A, ps, rcond=None)
    return coef  # [b0, b1]


def _fit_quadratic(qs: np.ndarray, ps: np.ndarray) -> Optional[np.ndarray]:
    """OLS kuadratik fit: p = b0 + b1*q + b2*q^2. En az 3 nokta gerek."""
    if len(qs) < 3:
        return None
    A = np.column_stack([np.ones_like(qs), qs, qs ** 2])
    coef, *_ = np.linalg.lstsq(A, ps, rcond=None)
    return coef  # [b0, b1, b2]


def _predict_linear(coef: np.ndarray, q: float) -> float:
    return float(coef[0] + coef[1] * q)


def _predict_quadratic(coef: np.ndarray, q: float) -> float:
    return float(coef[0] + coef[1] * q + coef[2] * (q ** 2))


def K1(canonical: np.ndarray, key: np.ndarray,
        copier_idx: int, source_idx: int, num_items: int,
        subgroup_exclusion: SubgroupExclusion = "source_only",
        ) -> Tuple[Optional[float], Dict[str, float]]:
    """K1 — lineer regresyon (Sotaridona-Meijer 2002, Eqn 6).

    Q_c = w_copier / I bilinerek, p̂*_c = beta_0 + beta_1 * Q_c.
    K1 = P(M >= m_cc) with M ~ Binomial(w_source, p̂*_c).

    Notation notu (madde 4b teyidi): Binomial deneme sayisi
    kaynagin yanlislari — Sotaridona 2002 Eqn 3-4. `w_source` /
    `w_copier` degisken adlari karisikligi onlemek icin.

    subgroup_exclusion:
      "source_only" (varsayilan, yayimlanmis tanim)
      "source_and_copier" (alternatif)
    """
    if copier_idx == source_idx:
        raise ValueError("copier == source olamaz")

    c = canonical[copier_idx]
    s = canonical[source_idx]
    w_copier = num_wrong(c, key)
    w_source = num_wrong(s, key)
    m_cc = matching_wrong(c, s, key)

    if w_source == 0:
        return None, {"reason": "w_source == 0"}

    exclude = _resolve_exclude_copier(subgroup_exclusion, copier_idx)
    qs, ps, _ = _subgroup_points(canonical, key, source_idx, num_items,
                                    copier_idx=exclude)
    if len(qs) < 2:
        return None, {"reason": "regression icin < 2 nokta", "n_points": len(qs)}

    coef = _fit_linear(qs, ps)
    if coef is None:
        return None, {"reason": "lineer fit basarisiz"}

    q_c = w_copier / num_items
    p_hat = _predict_linear(coef, q_c)
    # CopyDetect 1.3: if p1 >= 1 then p1=0.999; if p1 <= 0 then p1=0.001
    if p_hat >= 1.0:
        p_hat_clamped = 0.999
    elif p_hat <= 0.0:
        p_hat_clamped = 0.001
    else:
        p_hat_clamped = float(p_hat)
    K = _binomial_upper_tail(m_cc, w_source, p_hat_clamped)

    return K, {
        "p_hat": p_hat_clamped,
        "p_hat_raw": p_hat,
        "beta0": float(coef[0]),
        "beta1": float(coef[1]),
        "q_c": q_c,
        "w_source": w_source,
        "w_copier": int(w_copier),
        "m_cc": int(m_cc),
        "n_points": int(len(qs)),
        "subgroup_exclusion": subgroup_exclusion,
    }


def K2(canonical: np.ndarray, key: np.ndarray,
        copier_idx: int, source_idx: int, num_items: int,
        subgroup_exclusion: SubgroupExclusion = "source_only",
        ) -> Tuple[Optional[float], Dict[str, float]]:
    """K2 — kuadratik regresyon (Sotaridona-Meijer 2002, Eqn 7).

    p̂^_c = beta_0 + beta_1*Q_c + beta_2*Q_c^2.
    K2 = P(M >= m_cc) with M ~ Binomial(w_source, p̂^_c).

    En az 3 subgroup gerek. Aksi halde None.
    """
    if copier_idx == source_idx:
        raise ValueError("copier == source olamaz")

    c = canonical[copier_idx]
    s = canonical[source_idx]
    w_copier = num_wrong(c, key)
    w_source = num_wrong(s, key)
    m_cc = matching_wrong(c, s, key)

    if w_source == 0:
        return None, {"reason": "w_source == 0"}

    exclude = _resolve_exclude_copier(subgroup_exclusion, copier_idx)
    qs, ps, _ = _subgroup_points(canonical, key, source_idx, num_items,
                                    copier_idx=exclude)
    if len(qs) < 3:
        return None, {"reason": "regression icin < 3 nokta", "n_points": len(qs)}

    coef = _fit_quadratic(qs, ps)
    if coef is None:
        return None, {"reason": "kuadratik fit basarisiz"}

    q_c = w_copier / num_items
    p_hat = _predict_quadratic(coef, q_c)
    # CopyDetect 1.3: if p2 >= 1 then p2=0.999; if p2 <= 0 then p2=0.001
    if p_hat >= 1.0:
        p_hat_clamped = 0.999
    elif p_hat <= 0.0:
        p_hat_clamped = 0.001
    else:
        p_hat_clamped = float(p_hat)
    K = _binomial_upper_tail(m_cc, w_source, p_hat_clamped)

    return K, {
        "p_hat": p_hat_clamped,
        "p_hat_raw": p_hat,
        "beta0": float(coef[0]),
        "beta1": float(coef[1]),
        "beta2": float(coef[2]),
        "q_c": q_c,
        "w_source": w_source,
        "w_copier": int(w_copier),
        "m_cc": int(m_cc),
        "n_points": int(len(qs)),
        "subgroup_exclusion": subgroup_exclusion,
    }


# ── Poisson GLM (loglinear model) — S1/S2 icin ───────────

def _fit_poisson_loglinear(x: np.ndarray, y: np.ndarray,
                            max_iter: int = 100,
                            tol: float = 1e-12
                            ) -> Tuple[Optional[np.ndarray], Dict[str, float]]:
    """Basit Poisson GLM (log link) IRLS ile fit.

    Model: log(mu_j) = beta_0 + beta_1 * x_j, y_j ~ Poisson(mu_j)

    IRLS iterasyonu (Fisher scoring, log link icin):
      W = diag(mu)
      z = eta + (y - mu) / mu
      beta_new = (X^T W X)^{-1} X^T W z

    Sikilastirmalar (Madde 3):
    - Varsayilan tol=1e-12, max_iter=100.
    - Yakinsayamadiginda sessizce dönme; caller NOT_COMPUTABLE dondurur.
    - Yakinsama iterasyonu ("n_iter") ve son delta ("last_delta") meta'da.

    Not: R'in glm()'i ile birebir sonuc uretmez (baslangic degeri ve
    yakinsama kriteri farkli); S29'da iki asamali dogrulama gerek.
    Bunun icin S1/S2 caller'lari `fitted_lambda` disardan alabilecek
    sekilde ayrildi.

    Doner: (beta, meta). beta None -> yakinsamadi ya da singular.
    """
    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    n = len(x)
    if n < 2:
        return None, {"reason": "< 2 nokta", "n_iter": 0}
    if len(y) != n:
        raise ValueError("x ve y uzunluklari eslesmiyor")
    if (y < 0).any():
        raise ValueError("Poisson y negatif olamaz")

    X = np.column_stack([np.ones(n), x])
    y_shift = y + 0.5
    beta = np.array([np.log(y_shift.mean()), 0.0], dtype=np.float64)

    last_delta = float("inf")
    converged = False
    for it in range(1, max_iter + 1):
        eta = X @ beta
        eta_clipped = np.clip(eta, -30.0, 30.0)
        mu = np.exp(eta_clipped)
        mu_safe = np.maximum(mu, 1e-12)
        z = eta_clipped + (y - mu) / mu_safe
        W = mu_safe
        XtWX = X.T @ (W[:, None] * X)
        XtWz = X.T @ (W * z)
        try:
            beta_new = np.linalg.solve(XtWX, XtWz)
        except np.linalg.LinAlgError:
            return None, {"reason": "singular", "n_iter": it}
        if not np.all(np.isfinite(beta_new)):
            return None, {"reason": "non-finite", "n_iter": it}
        last_delta = float(np.max(np.abs(beta_new - beta)))
        beta = beta_new
        if last_delta < tol:
            converged = True
            break
    if not converged:
        return None, {
            "reason": f"not converged (last_delta={last_delta:.2e}, tol={tol})",
            "n_iter": max_iter,
            "last_delta": last_delta,
        }
    return beta, {"n_iter": it, "last_delta": last_delta, "converged": True}


def _g2_deviance(y_obs: np.ndarray, mu_hat: np.ndarray) -> float:
    """Poisson log-likelihood ratio test istatistigi (Sotaridona 2003 Eqn 10).

        G² = 2 Σ_r y_r · log(y_r / μ̂_r)

    y=0 terimleri konvansiyon geregi 0 (lim y→0 y·log(y) = 0).
    Girdilerin non-negative olmasi beklenir.
    """
    if len(y_obs) != len(mu_hat):
        raise ValueError("y_obs ve mu_hat uzunluklari eslesmeli")
    y = np.asarray(y_obs, dtype=np.float64)
    mu = np.asarray(mu_hat, dtype=np.float64)
    if (y < 0).any() or (mu <= 0).any():
        # mu > 0 gerekli (log(y/mu) tanimli olsun); y=0 -> katki 0
        # mu=0 hata sinirinda ise clamp
        mu = np.maximum(mu, 1e-300)
    with np.errstate(divide="ignore", invalid="ignore"):
        term = np.where(y > 0, y * np.log(y / mu), 0.0)
    return float(2.0 * term.sum())


def _g2_p_value(g2: float, df: int) -> Optional[float]:
    """G² p-degeri: chi2 sag kuyruk. df <= 0 ise None."""
    if df <= 0:
        return None
    if g2 < 0:
        return 1.0
    return float(stats.chi2.sf(g2, df))


G2_ALPHA = 0.01  # Sotaridona-Meijer 2003 s.10 esiği — S1/S2 icin model uyum kapisi.


def _poisson_upper_tail(m: int, mu: float) -> float:
    """P(X >= m) with X ~ Poisson(mu). scipy sf ile kuyruk-guvenli."""
    if m <= 0:
        return 1.0
    if mu <= 0.0:
        return 0.0
    return float(stats.poisson.sf(m - 1, mu))


def _upper_tail_flexible(m, mu: float, rounding: str) -> float:
    """P(X >= m) Poisson kuyruk. m int veya float; rounding="none" ise
    regularized incomplete gamma ile surekli approximation.
    """
    if isinstance(m, (int, np.integer)):
        return _poisson_upper_tail(int(m), mu)
    m = float(m)
    if m <= 0:
        return 1.0
    if mu <= 0.0:
        return 0.0
    from scipy.special import gammaincc
    return float(gammaincc(m, mu))


def _truncated_poisson_upper_tail(m: int, mu: float, upper: int) -> float:
    """Kesik ust kuyruk (Sotaridona 2003 / CopyDetect 1.3).

    S1 formulu (R'da):
        s1.index = (1 - ppois(m - 1, s1)) - (1 - ppois(ws, s1))

    Yani ust kuyruktan `upper` (ust sinir) OTESINDEKI kutle CIKARILIR.
    - m: gozlenen deger (m_cc)
    - mu: Poisson ortalamasi (s1 fitted lambda)
    - upper: ust sinir (S1: w_source, S2: n_items)

    Bu, degiskenin yalnizca [0, upper] araliginda tanimli oldugunu
    gozetir — bir kesik dagilim degil, kuyruk hesabinda 'imkansiz'
    olan bolgeyi cikarma.
    """
    if m <= 0:
        return 1.0 - _poisson_upper_tail(upper + 1, mu)
    if mu <= 0.0:
        return 0.0
    # P(X >= m) - P(X >= upper+1) = P(m <= X <= upper)
    lower = _poisson_upper_tail(m, mu)
    exclude = _poisson_upper_tail(upper + 1, mu)
    return max(0.0, lower - exclude)


# ── S1 (Sotaridona-Meijer 2003, Eqn 8) ────────────────────

def _subgroup_mean_M(canonical: np.ndarray, key: np.ndarray,
                      source_idx: int,
                      copier_idx: Optional[int] = None
                      ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Her yanlis sayisi subgroup'u icin ortalama M (matching wrong).

    Source (ve verildiyse copier) subgroup fit'inden hariç tutulur.
    Bkz. _subgroup_points'daki # AMBIGUOUS notu.

    Doner: (w_r_array, mbar_r_array, all_wrongs)
    """
    n = canonical.shape[0]
    s = canonical[source_idx]
    all_wrongs = np.array([num_wrong(canonical[j], key) for j in range(n)],
                           dtype=np.int64)
    unique_ws = np.unique(all_wrongs)
    ws: List[int] = []
    mbars: List[float] = []
    for w in unique_ws:
        idx = np.where(all_wrongs == w)[0]
        mask = idx != source_idx
        if copier_idx is not None:
            mask = mask & (idx != copier_idx)
        idx = idx[mask]
        if len(idx) == 0:
            continue
        ms = np.array([matching_wrong(canonical[j], s, key) for j in idx],
                       dtype=np.float64)
        ws.append(int(w))
        mbars.append(float(ms.mean()))
    return (np.array(ws, dtype=np.float64),
            np.array(mbars, dtype=np.float64),
            all_wrongs)


def S1(canonical: np.ndarray, key: np.ndarray,
        copier_idx: int, source_idx: int,
        subgroup_exclusion: SubgroupExclusion = "source_only",
        fitted_mu_c: Optional[float] = None,
        ) -> Tuple[Optional[float], Dict[str, float]]:
    """S1 index (Sotaridona-Meijer 2003, Eqn 8).

    M ~ Poisson(mu). Loglinear model:
        log(mu_r) = beta_0 + beta_1 * w_r  (Eqn 9)

    Copier'in subgroup'u icin mu_c' tahmin edilir:
        mu_c' = exp(beta_0 + beta_1 * w_copier)  (Eqn 10 metninde)

    S1 = P(M >= m_cc | Poisson(mu_c'))

    Parametreler:
        subgroup_exclusion: "source_only" (varsayilan, yayimlanmis tanim)
                             veya "source_and_copier".
        fitted_mu_c: Disardan tahmin edilmis λ_c'. Verilmezse dahili IRLS
                     ile fit edilir. S29 iki asamali dogrulamasi icin
                     (Asama A: R'in fit'i, Asama B: butun ciklus).

    Regresyon icin en az 2 subgroup gerek (fitted_mu_c verilmediyse).
    """
    if copier_idx == source_idx:
        raise ValueError("copier == source olamaz")

    c = canonical[copier_idx]
    s = canonical[source_idx]
    w_copier = num_wrong(c, key)
    m_cc = matching_wrong(c, s, key)

    # Source w for truncation upper bound (Sotaridona 2003 kesik Poisson).
    w_source = num_wrong(canonical[source_idx], key)

    # Asama A: fitted_mu_c disardan verildi -> GLM'i atla
    if fitted_mu_c is not None:
        if fitted_mu_c < 0:
            raise ValueError("fitted_mu_c negatif olamaz")
        mu_ext = float(fitted_mu_c)
        # CopyDetect: s1 clamp to <= w_source
        mu_ext = min(mu_ext, float(w_source)) if w_source > 0 else mu_ext
        S = _truncated_poisson_upper_tail(m_cc, mu_ext, w_source)
        return S, {
            "mu_c": mu_ext,
            "w_copier": int(w_copier),
            "w_source": int(w_source),
            "m_cc": int(m_cc),
            "subgroup_exclusion": subgroup_exclusion,
            "fit_source": "external",
        }

    exclude = _resolve_exclude_copier(subgroup_exclusion, copier_idx)
    ws, mbars, _ = _subgroup_mean_M(canonical, key, source_idx,
                                       copier_idx=exclude)
    if len(ws) < 2:
        return None, {"reason": "< 2 subgroup", "n_points": int(len(ws))}

    beta, fit_meta = _fit_poisson_loglinear(ws, mbars)
    if beta is None:
        return None, {
            "reason": f"poisson GLM: {fit_meta.get('reason','')}",
            **fit_meta,
        }

    # G² model uyum istatistigi (Eqn 10). df = R - 2.
    mu_hat = np.exp(np.clip(beta[0] + beta[1] * ws, -30.0, 30.0))
    g2 = _g2_deviance(mbars, mu_hat)
    g2_df = int(len(ws)) - 2
    g2_p = _g2_p_value(g2, g2_df)

    mu_c = float(np.exp(np.clip(beta[0] + beta[1] * w_copier, -30.0, 30.0)))
    # CopyDetect 1.3: if s1 >= ws then s1 = ws (sinir kirpma)
    if w_source > 0 and mu_c > w_source:
        mu_c = float(w_source)
    S = _truncated_poisson_upper_tail(m_cc, mu_c, w_source)

    return S, {
        "mu_c": mu_c,
        "beta0": float(beta[0]),
        "beta1": float(beta[1]),
        "w_copier": int(w_copier),
        "w_source": int(w_source),
        "m_cc": int(m_cc),
        "n_points": int(len(ws)),
        "subgroup_exclusion": subgroup_exclusion,
        "fit_source": "internal_irls",
        "n_iter": int(fit_meta.get("n_iter", 0)),
        "last_delta": float(fit_meta.get("last_delta", 0.0)),
        "g2": g2,
        "g2_df": g2_df,
        "g2_p_value": g2_p,
    }


# ── S2 (Sotaridona-Meijer 2003, Eqn 13-15) ────────────────

DeltaVariant = Literal["reference", "paper_text"]


def _delta_weight(p_hat: float, guessing: float,
                    variant: str = "reference") -> float:
    """delta_{i*rj} — S2 icin dogru-cevap kopya kaniti agirligi.

    Iki varyant:

    "reference" (varsayilan) — CopyDetect 1.3 `ks12()` implementasyonu:
        d2 = -(1 + g) / g
        base = ((1 + g) / (1 - g)) * e
        δ = base^(prob * d2)

        4-secenek (g=0.25):
        prob=0.00 -> δ=1.000  (peer bilmiyor, tam kanit)
        prob=0.25 -> δ=0.151
        prob=0.50 -> δ=0.023
        prob=1.00 -> δ~0.00052 (peer biliyor, kanit ~ 0)

        Sotaridona 2003 Figure 1 grafigi ve conditions (1)-(2) ile
        birebir uyumlu (P->1 iken δ->0 dogru davranis).

    "paper_text" — PDF metin-cikarma hatasi olabilecek eski yorum:
        d2 = 1 - g, d1 = g/(1-g), δ = d1^(d2*P)
        P=1'de 0.328 tabaninda takilir — Figure 1 ile UYUMSUZ.
        Karsilastirma amacli korunmustur.

    S29 kalibrasyonu ile bulundu (CopyDetect 1.3 similarity2 kaynak
    kodu). "reference" formul dogru. Onceki "paper_text" yorumu
    S2 duyarliligini yaniltici derecede dusurmustu (H3 bulgusunu geri
    aliyoruz — δ dogru yorumlaninca S2 beklendik davranir).

    Sotaridona & Meijer (2003), Eqn 13 (arsiv metni):
        δ_{i*rj} = f(P_{i*rj}) = (d1)^(d2 · P_{i*rj})
        d2 = 1 − g
        d1 = g / d2 = g / (1 − g)

    Ornek degerler (g = 0.2, 5-secenek testi):
        d1 = 0.25, d2 = 0.8
        δ(0.0) = 1.00      → peer bilmiyor; source dogru ise kopya kaniti tam
        δ(0.5) = 0.574     → orta yol
        δ(1.0) = 0.328     → peer biliyor; kopya kaniti azalir AMA SIFIR DEGIL
        δ(1.0)/δ(0.0) = 0.328

    Yorum:
    - δ = 0 hicbir zaman gerceklesmez (P ∈ [0, 1] icin δ >= 0.328).
    - δ tam olarak "kopya kaniti agirligi" degil, "azaltilmis kanit" —
      cok bilinen bir dogru cevap (P=1) icin δ ≈ 0.33, tam sifir degil.

    Makale konusu (Sotaridona 2003 s. 12):
        Condition (1): "f(Pirj) approaches 0 as Pi*rj approaches 1"
        Condition (2): "f(Pirj) approaches 1 as Pi*rj approaches 0"

    Formul Condition (2)'yi tam saglar (P=0 → δ=1) ancak Condition (1)'i
    TAM saglar sekilde degil — sadece asagi dogru azalir. Makale bunu
    "approaches" kelimesiyle mumkun kilar. R (CopyDetect) implementasyonu
    da bu formulu kullanir; boylece S29 karsilastirmasinda tam esitlik
    beklenir.

    # AMBIGUOUS #3 — cozum: Sotaridona 2003 Eqn 13'e tam sadik.
    # Alternatif formuller (ornek: (1-P)^d) makale-di sapmadir.

    """
    import math
    if not (0.0 <= p_hat <= 1.0):
        p_hat = max(0.0, min(1.0, p_hat))
    if variant == "reference":
        d2 = -(1.0 + guessing) / guessing
        base = ((1.0 + guessing) / (1.0 - guessing)) * math.e
        return float(base ** (p_hat * d2))
    elif variant == "paper_text":
        d2 = 1.0 - guessing
        d1 = guessing / d2
        return float(d1 ** (d2 * p_hat))
    else:
        raise ValueError(f"bilinmeyen delta variant: {variant}")


def _weighted_M_star(canonical: np.ndarray, key: np.ndarray,
                      rj_idx: int, source_idx: int,
                      subgroup_indices: np.ndarray,
                      guessing: float,
                      delta_variant: str = "reference",
                      return_parts: bool = False):
    """M*_rj (Eqn 14): matching_wrong(rj, s) + Σ delta_{i*rj} over items
    where source is CORRECT and rj gives same (correct) answer.

    return_parts=True ise (m_wrong, delta_sum) tuple doner — S2'de
    R referansi delta_sum'i AYRI ceiling'e almasi icin.
    """
    rj = canonical[rj_idx]
    s = canonical[source_idx]
    # Matching incorrect
    m_incorrect = float(matching_wrong(rj, s, key))
    # Matching correct: source dogru olan maddelerde, rj de ayni cevabi verirse
    n_items = len(key)
    delta_sum = 0.0
    for i in range(n_items):
        u_is = int(s[i])
        # Sadece source'un dogru maddesi
        if u_is != int(key[i]):
            continue
        if u_is < 1:
            continue  # source bos/coklu — dahil degil
        u_irj = int(rj[i])
        if u_irj != u_is:
            continue  # rj bu maddede ya bos ya farkli — matching correct DEGIL
        # P_{i*rj}: subgroup icinde bu maddede source ile ayni cevap veren orani
        # (Eqn 12: sum(A_{i*rj}) / J_r)
        matches = 0
        for j in subgroup_indices:
            if int(canonical[j, i]) == u_is:
                matches += 1
        p_hat = matches / len(subgroup_indices) if len(subgroup_indices) > 0 else 0.0
        delta_sum += _delta_weight(p_hat, guessing, variant=delta_variant)
    if return_parts:
        return m_incorrect, delta_sum
    return m_incorrect + delta_sum


MStarRounding = Literal["round", "floor", "none"]


def S2(canonical: np.ndarray, key: np.ndarray,
        copier_idx: int, source_idx: int,
        n_options: int,
        subgroup_exclusion: SubgroupExclusion = "source_only",
        fitted_mu_c: Optional[float] = None,
        m_star_rounding: MStarRounding = "round",
        ) -> Tuple[Optional[float], Dict[str, float]]:
    """S2 index (Sotaridona-Meijer 2003, Eqn 15).

    M* = matching_wrong + Σ delta_{i*} over correct-by-source items.
    delta Eqn 13 with g = 1 / n_options.

    M*_rj Poisson yaklaşımı; loglinear regresyon Eqn 9 forma
    (mean of M*_r). M* integer'e yuvarlanir (Sotaridona 2003, s. 14).
    S2 = P(M* >= m*_cc | Poisson(mu*_c')).

    Parametreler:
        subgroup_exclusion: "source_only" (varsayilan) veya "source_and_copier".
        fitted_mu_c: Disardan tahmin edilmis λ_c'. Verilmezse dahili IRLS.
        m_star_rounding: "round" (Sotaridona 2003 sadik, varsayilan),
                          "floor" (asagi yuvarla — daha muhafazakar iddia),
                          "none" (yuvarlamadan float Poisson gamma-approx).
                          H2 arastirmasi icin — YAYINLANMIS DEFAULT DEGISME.
    """
    if copier_idx == source_idx:
        raise ValueError("copier == source olamaz")

    guessing = 1.0 / n_options
    n = canonical.shape[0]
    c = canonical[copier_idx]
    w_copier = num_wrong(c, key)

    all_wrongs = np.array([num_wrong(canonical[j], key) for j in range(n)],
                           dtype=np.int64)

    # Copier'in subgroup'u — P_{i*rj} tahmini icin emsaller (source her
    # zaman haric; copier subgroup_exclusion moduna gore).
    copier_subgroup = np.where(all_wrongs == w_copier)[0]
    exclude_from_ref = _resolve_exclude_copier(subgroup_exclusion, copier_idx)
    mask = copier_subgroup != source_idx
    if exclude_from_ref is not None:
        mask = mask & (copier_subgroup != exclude_from_ref)
    copier_subgroup = copier_subgroup[mask]
    if len(copier_subgroup) == 0:
        return None, {"reason": "copier subgroup bos"}

    # m*_cc: copier'in M* degeri.
    # CopyDetect 1.3 ks12(): mm = ceiling(sum(weight[wc+1, cm])) + m
    # Yani: delta_sum AYRICA ceiling'e alinip m (matching_wrong) eklenir.
    # Bizim eski kod tum toplami round yapiyordu — bu S2'de sistemli fark
    # yaratiyordu (kalibrasyon: bizim m*=1 vs R m*=2 turu farklar).
    import math
    m_wrong, delta_sum = _weighted_M_star(
        canonical, key, copier_idx, source_idx, copier_subgroup, guessing,
        return_parts=True,
    )
    m_star_cc_float = m_wrong + delta_sum
    if m_star_rounding == "round":
        # Referans: ceiling(delta_sum) + m_wrong
        m_star_cc = int(math.ceil(delta_sum)) + int(m_wrong)
    elif m_star_rounding == "floor":
        m_star_cc = int(np.floor(delta_sum)) + int(m_wrong)
    else:  # "none" — surekli Poisson gamma
        m_star_cc = m_star_cc_float

    n_items_total = canonical.shape[1]

    # Asama A: fitted_mu_c disardan -> GLM'i atla
    if fitted_mu_c is not None:
        if fitted_mu_c < 0:
            raise ValueError("fitted_mu_c negatif olamaz")
        mu_ext = float(fitted_mu_c)
        # CopyDetect: if s2 >= n_items then s2 = n_items
        if mu_ext > n_items_total:
            mu_ext = float(n_items_total)
        # Kesik Poisson: [m_star_cc, n_items] araligi
        if isinstance(m_star_cc, (int, np.integer)):
            S = _truncated_poisson_upper_tail(int(m_star_cc), mu_ext,
                                                 n_items_total)
        else:
            S = _upper_tail_flexible(m_star_cc, mu_ext, m_star_rounding)
        return S, {
            "mu_c": mu_ext,
            "w_copier": int(w_copier),
            "m_star_cc": (int(m_star_cc) if isinstance(m_star_cc, (int, np.integer))
                          else float(m_star_cc)),
            "m_star_cc_raw": float(m_star_cc_float),
            "guessing": guessing,
            "subgroup_exclusion": subgroup_exclusion,
            "m_star_rounding": m_star_rounding,
            "fit_source": "external",
        }

    # Her subgroup icin M*_r ortalamasi (source her zaman + mod'a gore copier)
    # CopyDetect 1.3 ks12 (similarity2.r):
    #   y_r = mean(matching_wrong_r) + ceiling(mean(delta_sum_r))
    # Ceiling SUBGROUP ORTALAMASI uzerinde (delta_bar), per-peer DEGIL.
    # w_r range 0..n_items (empty subgroup'lar GLM'de NA olarak atlanır).
    unique_ws = np.arange(canonical.shape[1] + 1)
    ws: List[float] = []
    mstar_bars: List[float] = []
    for w in unique_ws:
        idx = np.where(all_wrongs == w)[0]
        submask = idx != source_idx
        if exclude_from_ref is not None:
            submask = submask & (idx != exclude_from_ref)
        idx = idx[submask]
        if len(idx) == 0:
            continue
        m_wrong_peers = []
        delta_peers = []
        for j in idx:
            mw, ds = _weighted_M_star(
                canonical, key, int(j), source_idx, idx, guessing,
                return_parts=True,
            )
            m_wrong_peers.append(mw)
            delta_peers.append(ds)
        m_wrong_peers = np.array(m_wrong_peers, dtype=np.float64)
        delta_peers = np.array(delta_peers, dtype=np.float64)
        m_wrong_bar = float(m_wrong_peers.mean())
        delta_bar = float(delta_peers.mean())
        if m_star_rounding == "round":
            y_w = m_wrong_bar + math.ceil(delta_bar)
        elif m_star_rounding == "floor":
            y_w = m_wrong_bar + math.floor(delta_bar)
        else:
            y_w = m_wrong_bar + delta_bar
        ws.append(float(w))
        mstar_bars.append(y_w)
    if len(ws) < 2:
        return None, {"reason": "< 2 subgroup"}

    ws_arr = np.array(ws)
    mstar_arr = np.array(mstar_bars)
    beta, fit_meta = _fit_poisson_loglinear(ws_arr, mstar_arr)
    if beta is None:
        return None, {
            "reason": f"poisson GLM: {fit_meta.get('reason','')}",
            **fit_meta,
        }

    # G² model uyum istatistigi (Eqn 10 M* uzerinden). df = R - 2.
    mu_hat_all = np.exp(np.clip(beta[0] + beta[1] * ws_arr, -30.0, 30.0))
    g2 = _g2_deviance(mstar_arr, mu_hat_all)
    g2_df = int(len(ws_arr)) - 2
    g2_p = _g2_p_value(g2, g2_df)

    mu_c = float(np.exp(np.clip(beta[0] + beta[1] * w_copier, -30.0, 30.0)))
    # CopyDetect: if s2 >= n_items then s2 = n_items
    if mu_c > n_items_total:
        mu_c = float(n_items_total)
    # Kesik Poisson upper tail: [m_star_cc, n_items] araligi
    if isinstance(m_star_cc, (int, np.integer)):
        S = _truncated_poisson_upper_tail(int(m_star_cc), mu_c, n_items_total)
    else:
        S = _upper_tail_flexible(m_star_cc, mu_c, m_star_rounding)

    return S, {
        "mu_c": mu_c,
        "beta0": float(beta[0]),
        "beta1": float(beta[1]),
        "w_copier": int(w_copier),
        "m_star_cc": (int(m_star_cc) if isinstance(m_star_cc, (int, np.integer))
                       else float(m_star_cc)),
        "m_star_cc_raw": float(m_star_cc_float),
        "guessing": guessing,
        "n_points": int(len(ws)),
        "subgroup_exclusion": subgroup_exclusion,
        "m_star_rounding": m_star_rounding,
        "fit_source": "internal_irls",
        "n_iter": int(fit_meta.get("n_iter", 0)),
        "last_delta": float(fit_meta.get("last_delta", 0.0)),
        "g2": g2,
        "g2_df": g2_df,
        "g2_p_value": g2_p,
    }


__all__ = [
    "wrong_indices",
    "num_wrong",
    "matching_wrong",
    "K_empirical",
    "K_star",
    "K1",
    "K2",
    "S1",
    "S2",
]
