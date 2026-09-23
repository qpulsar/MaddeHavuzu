"""
Cheating — Tanimlayici Olcumler
================================
Ortak yanlis sayisi/orani, ortak bos, uyusma orani, en uzun ardisik
ortak-yanlis blogu. Olasilik hesabi degil — kanit sunumu icin sayim.

v1: temel fonksiyonlar. Girdi kanonik uzayda yanit dizileridir.
"""

from __future__ import annotations

from typing import Dict

import numpy as np


def _valid_mask(row: np.ndarray) -> np.ndarray:
    """Gecerli (bos/coklu olmayan) pozisyonlar. 1..K arasi degerler gecerli."""
    return row >= 1


def common_correct(a: np.ndarray, b: np.ndarray, key: np.ndarray) -> int:
    """Iki ogrencinin ortak DOGRU cevap sayisi. Kanonik uzayda cagrilir."""
    a_correct = (a == key)
    b_correct = (b == key)
    return int(np.sum(a_correct & b_correct))


def common_wrong(a: np.ndarray, b: np.ndarray, key: np.ndarray) -> int:
    """Iki ogrencinin ayni yanlisi verdigi madde sayisi.

    Sart: iki cevap da gecerli (1..K), ikisi de ayni, ve anahtardan farkli.
    Bu, kopya tespitinin **temel** girdisi — spec §3.1 vurgusu.
    """
    valid = _valid_mask(a) & _valid_mask(b)
    same = (a == b)
    wrong_a = (a != key)
    return int(np.sum(valid & same & wrong_a))


def common_blank(a: np.ndarray, b: np.ndarray) -> int:
    """Iki ogrencinin de bos biraktigi madde sayisi."""
    return int(np.sum((a == 0) & (b == 0)))


def agreement_rate(a: np.ndarray, b: np.ndarray) -> float:
    """Ayni cevabi verme orani (bos/coklu dahil). Sadece iki cevap da
    ayni ise sayilir; bos-bos da eslesme sayilir. Payda: toplam madde."""
    if len(a) == 0:
        return 0.0
    return float(np.mean(a == b))


def longest_common_wrong_run(a: np.ndarray, b: np.ndarray,
                              key: np.ndarray) -> int:
    """En uzun ardisik ortak-yanlis blogu.

    Bir konum "ortak yanlis" ise: iki cevap da gecerli + ayni + anahtardan
    farkli. Ardisik olanlarin en uzun serisi.
    """
    valid = _valid_mask(a) & _valid_mask(b)
    same = (a == b)
    wrong_a = (a != key)
    hits = valid & same & wrong_a
    if not hits.any():
        return 0
    # Ardisik True'larin en uzun serisi
    max_run = cur = 0
    for v in hits:
        if v:
            cur += 1
            if cur > max_run:
                max_run = cur
        else:
            cur = 0
    return int(max_run)


def descriptive_pair(a: np.ndarray, b: np.ndarray, key: np.ndarray) -> Dict[str, float]:
    """Bir cift icin tum tanimlayici olcumleri sozluk halinde don."""
    n = len(a)
    cw = common_wrong(a, b, key)
    return {
        "n_items": n,
        "common_correct": common_correct(a, b, key),
        "common_wrong": cw,
        "common_wrong_rate": cw / n if n else 0.0,
        "common_blank": common_blank(a, b),
        "agreement_rate": agreement_rate(a, b),
        "longest_common_wrong_run": longest_common_wrong_run(a, b, key),
    }


__all__ = [
    "common_correct",
    "common_wrong",
    "common_blank",
    "agreement_rate",
    "longest_common_wrong_run",
    "descriptive_pair",
]
