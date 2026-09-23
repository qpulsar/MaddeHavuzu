"""
Cheating — Birey-uyum Indeksleri (U3, H^T)
============================================
Kisi cevap deseninin Guttman-uyumlulugunu olcen istatistikler. Kolay
maddede yanlis + zor maddede dogru gibi "anti-Guttman" desenler kopya
sinyallerinden biri (kopyacinin yetenegi disi puanlar).

Kaynak
------
- U3: van der Flier (1982). "Deviant response patterns and comparability
  of test scores". J. Cross-Cultural Psychology.
  # AMBIGUOUS: cheating/vanderflier1982.pdf taranmis goruntu (OCR yok),
  # tam formul metni okunamiyor. Standart yorum Meijer & Sijtsma (2001)
  # "Methodology review: Evaluating person fit" (APM 25, 107-135)
  # review makalesine dayaniyor — bu formul yaygin kabul goruyor.
- H^T: Sijtsma & Meijer (1992). "A method for investigating the intersection
  of item response functions in Mokken's nonparametric IRT model". APM 16,
  149-157. Denklemler (5) ve (6) — cheating/sijtsma1992.pdf.

Girdi
-----
- responses: (n_students, n_items), 0/1 ikili puanli (dogru=1, yanlis=0).
  ExamData.canonical (1..K secenek) icin, kopya modulundeki cagri:
      binary = (canonical == key).astype(np.int8)
- Bos ve coklu isaret (0, -1) yanlis (0) sayilir — Guttman modeli yanlis
  vs. dogru ayrimi yapar.

Her iki fonksiyon da (n_students,) uzunlugunda skor dizisi doner. NaN =
tanimlanamiyor (ornek: n=1, ya da tum skorlar ozdes).
"""

from __future__ import annotations


import numpy as np


def to_binary_matrix(canonical: np.ndarray, key: np.ndarray) -> np.ndarray:
    """(n_students, n_items) 1..K matrisini 0/1 puanli matrise cevir.

    # AMBIGUOUS: Bos yanit (0) ve coklu isaret (-1) her ikisi de "yanlis"
    #   (0) olarak sayilir. Guttman modeli sadece dogru/yanlis ayrimini
    #   kabul ediyor — eksik veriyi yanlis saymak konservatif secim.
    #   Alternatif yorumlar (eksik veriyi cikarma, veya coklu isareti
    #   0.5 sayma) literaturde var. Kararimiz: konservatif (yanlis).
    """
    return (canonical == key).astype(np.int8)


# ── U3 (van der Flier 1982) ──────────────────────────────

def U3(binary: np.ndarray, eps: float = 1e-6) -> np.ndarray:
    """Kisi bazli U3 skorlari.

    Meijer-Sijtsma (2001) review, van der Flier'a atfeder:

        α_g = log(π_g / (1 - π_g))    (logit-difficulty)

    Kisi i icin, maddeleri π'ye gore AZALAN sirala (en kolay ilk).
    X_i = kisi i'nin toplam dogru sayisi.
    u_ig^G = Guttman-ideal: en kolay X_i madde 1, geri kalan 0
    u_ig^A = anti-Guttman: en zor X_i madde 1, geri kalan 0

        U3_i = ( Σ α_g (u_ig^G - u_ig)     )  /  ( Σ α_g (u_ig^G - u_ig^A) )

    - U3 ∈ [0, 1] (Guttman ideali ile anti-Guttman arasi lineer).
    - U3_i = 0 -> mukemmel Guttman fit (kolayin hepsi dogru, zorun hepsi yanlis)
    - U3_i = 1 -> tam anti-Guttman (kolayin hepsi yanlis, zorun hepsi dogru) — kopyaci sinyali

    Kenar durumlari:
    - X_i = 0 veya X_i = k: numerator = 0 payda = 0 -> tanimlanamaz (nan).
    - Bir maddenin π_g = 0 veya 1 olmasi -> α_g = ±inf. Bunlari clip et:
      π clamp [eps, 1-eps].
    - Tum π'ler ozdes -> Guttman siralama tanimsiz; U3 anlamsiz (nan).

    # AMBIGUOUS: van der Flier orijinali (taranmis PDF, OCR yok) ile
    #   direkt karsilastirma yapamiyoruz. R (`PerFit` paketi) veya
    #   `mokken` paketi ile S29'da hizalanacak.
    """
    if binary.ndim != 2:
        raise ValueError("binary 2D olmali")
    n_students, n_items = binary.shape
    if n_students == 0 or n_items == 0:
        return np.array([], dtype=np.float64)

    # Madde zorlugu (populasyon oranı doğru)
    pi = binary.mean(axis=0).astype(np.float64)
    pi = np.clip(pi, eps, 1.0 - eps)
    alpha = np.log(pi / (1.0 - pi))  # log-odds

    # Maddeleri KOLAYDAN ZORA sirala: pi azalan (en yuksek pi = kolay = ilk)
    order = np.argsort(-pi, kind="stable")
    alpha_sorted = alpha[order]
    binary_sorted = binary[:, order].astype(np.int8)

    scores = binary_sorted.sum(axis=1)  # X_i (int)
    out = np.full(n_students, np.nan, dtype=np.float64)

    for i in range(n_students):
        X = int(scores[i])
        if X == 0 or X == n_items:
            continue  # tanimlanamaz
        # Guttman ideal: ilk X madde = 1, geri kalan = 0
        u_G = np.zeros(n_items, dtype=np.int8)
        u_G[:X] = 1
        # Anti-Guttman: son X madde = 1, oncekiler 0
        u_A = np.zeros(n_items, dtype=np.int8)
        u_A[-X:] = 1
        u_actual = binary_sorted[i]

        numer = float(np.dot(alpha_sorted, (u_G - u_actual)))
        denom = float(np.dot(alpha_sorted, (u_G - u_A)))
        if denom <= 0.0:
            continue
        out[i] = numer / denom
    return out


# ── H^T (Sijtsma & Meijer 1992) ──────────────────────────

def HT(binary: np.ndarray) -> np.ndarray:
    """Kisi bazli H^T skorlari (Sijtsma-Meijer 1992, Eqn 6).

    P_i = kisi i'nin dogru sayisi orani (X_i / k)
    P_ij = kisi i ve j'nin ikisinin de dogru oldugu madde orani (X_ij / k)
    σ_ij = P_ij - P_i * P_j  (kisi kovaryansi)
    σ_ij(max) = min(P_i, P_j) * (1 - max(P_i, P_j))
      (Eqn 5'te "i < j implies P_i ≤ P_j" varsayilmis; simetrik yazim)

    H^T_i = Σ_{j ≠ i} σ_ij  /  Σ_{j ≠ i} σ_ij(max)

    - H^T_i ≥ 0 -> Mokken non-parametric IRT modeli ile uyumlu
    - H^T_i < 0 -> IRF'lerin kesisimine isaret (anti-fit)

    Kenar durumlari:
    - P_i = 0 veya P_i = 1: kovaryans tanimi anlamsiz (kisi'nin variyansi 0).
      Bu kisinin σ_ij(max) tumu 0 -> payda 0 -> nan.
    - n_students < 2: nan.
    """
    if binary.ndim != 2:
        raise ValueError("binary 2D olmali")
    n_students, n_items = binary.shape
    if n_students < 2 or n_items == 0:
        return np.full(n_students, np.nan, dtype=np.float64)

    X = binary.sum(axis=1).astype(np.float64)  # (n,)
    P = X / n_items  # (n,)
    # P_ij = (binary[i] . binary[j]) / n_items    (dot product / k)
    # Vektorlestir: binary @ binary.T / n_items -> (n, n)
    Xij = binary.astype(np.float64) @ binary.astype(np.float64).T
    P_ij = Xij / n_items
    P_i = P[:, None]  # column
    P_j = P[None, :]  # row
    sigma = P_ij - P_i * P_j  # (n, n)
    # Sigma max: min(P_i, P_j) * (1 - max(P_i, P_j))
    P_min = np.minimum(P_i, P_j)
    P_max = np.maximum(P_i, P_j)
    sigma_max = P_min * (1.0 - P_max)

    # Kosegen (i == j) toplama dahil olmasin
    np.fill_diagonal(sigma, 0.0)
    np.fill_diagonal(sigma_max, 0.0)

    numer = sigma.sum(axis=1)
    denom = sigma_max.sum(axis=1)

    out = np.full(n_students, np.nan, dtype=np.float64)
    mask = denom > 0.0
    out[mask] = numer[mask] / denom[mask]
    return out


__all__ = ["U3", "HT", "to_binary_matrix"]
