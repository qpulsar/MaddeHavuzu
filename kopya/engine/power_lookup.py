"""
Guc Duyarlilik Gostergesi

36 hucrelik simulasyon tablosundan bir sinavin parametrelerine (n,
k_valid) en yakin hucreleri bulup K1 gucu tahmini uretir. Bu bir kesin
kestirim degil — buyukluk mertebesi bilgisi. UI'da tabloya bagli bir
"bu koşullarda tespit olasiligi" gostergesi olarak kullanilir.

Kalibrasyon kaynagi
-------------------
- `cheating/simulation/data/pair_results.parquet` (36 hücre × 1000 rep,
  16.97M çift, spec §1)
- Hücre başı K1 gücü (α = 0.01) tablonun ana metriği. K1 tüm koşullarda
  en yüksek güç veren indeks (bkz. FINDINGS.md §0).
- Gerekçe: Sotaridona-Meijer 2003 protokolüne sadık NRM verisi;
  I. tip hata nominal α altında.

Onbelege
--------
- Bu tablo yalnız simülasyon rejimi (NRM, `random` mekanizma,
  kopyacı oranı %5) icin gecerli. Farkli rejim → tablo yeniden
  kalibre edilmeli.
- Simülasyonun literatur değerine ulaşamadığı S ailesi için ayrı
  tahmin doğru olmayabilir; kullanıcıya sadece "yaklaşık K1 gücü"
  gösterilir. Bkz. FINDINGS.md §1.
"""

from __future__ import annotations

import json
import os
from functools import lru_cache
from typing import Dict, Optional, Tuple



# Hardcoded fallback — simulation/summary/summary_tables.json yoksa
# (canlı sistemde bu tablo repoda kalıcı; yeniden koşum gerektirmez).
_FALLBACK_POWER_K1 = {
    # (n, n_items, pct) -> K1 gücü (α = 0.01)
    (20, 20, 0.10): 0.006, (20, 20, 0.20): 0.027, (20, 20, 0.40): 0.150,
    (20, 40, 0.10): 0.017, (20, 40, 0.20): 0.071, (20, 40, 0.40): 0.454,
    (30, 20, 0.10): 0.008, (30, 20, 0.20): 0.024, (30, 20, 0.40): 0.209,
    (30, 40, 0.10): 0.018, (30, 40, 0.20): 0.086, (30, 40, 0.40): 0.503,
    (40, 20, 0.10): 0.009, (40, 20, 0.20): 0.036, (40, 20, 0.40): 0.204,
    (40, 40, 0.10): 0.019, (40, 40, 0.20): 0.085, (40, 40, 0.40): 0.488,
    (60, 20, 0.10): 0.007, (60, 20, 0.20): 0.037, (60, 20, 0.40): 0.210,
    (60, 40, 0.10): 0.023, (60, 40, 0.20): 0.098, (60, 40, 0.40): 0.502,
    (100, 20, 0.10): 0.010, (100, 20, 0.20): 0.040, (100, 20, 0.40): 0.222,
    (100, 40, 0.10): 0.026, (100, 40, 0.20): 0.106, (100, 40, 0.40): 0.535,
    (200, 20, 0.10): 0.011, (200, 20, 0.20): 0.038, (200, 20, 0.40): 0.230,
    (200, 40, 0.10): 0.023, (200, 40, 0.20): 0.113, (200, 40, 0.40): 0.542,
}

SIM_N_GRID = (20, 30, 40, 60, 100, 200)
SIM_K_GRID = (20, 40)
SIM_PCT_GRID = (0.10, 0.20, 0.40)


@lru_cache(maxsize=1)
def _load_power_table() -> Dict[Tuple[int, int, float], float]:
    """Simulation'dan K1 gucu tablosu (36 hucre)."""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "summary_tables.json")
    if not os.path.exists(path):
        return dict(_FALLBACK_POWER_K1)

    try:
        with open(path, "r", encoding="utf-8") as f:
            d = json.load(f)
        # table2: guc × index × n × k × pct. K1'i filtrele.
        table: Dict[Tuple[int, int, float], float] = {}
        for c in d.get("table2", {}).get("cells", []):
            if c.get("index") != "K1":
                continue
            n = int(c["n"]); k = int(c["n_items"]); pct = float(c["pct"])
            rate = c.get("rate")
            if rate is not None:
                table[(n, k, pct)] = float(rate)
        return table if table else dict(_FALLBACK_POWER_K1)
    except Exception:
        return dict(_FALLBACK_POWER_K1)


def _nearest(x: int | float, grid: Tuple) -> Tuple:
    """Grid'de x'e en yakın iki noktayı döndür (lineer interpolasyon için)."""
    grid_sorted = sorted(grid)
    if x <= grid_sorted[0]:
        return grid_sorted[0], grid_sorted[0]
    if x >= grid_sorted[-1]:
        return grid_sorted[-1], grid_sorted[-1]
    for i in range(len(grid_sorted) - 1):
        if grid_sorted[i] <= x <= grid_sorted[i + 1]:
            return grid_sorted[i], grid_sorted[i + 1]
    return grid_sorted[-1], grid_sorted[-1]


def _lin_interp(x: float, x0: float, x1: float,
                 y0: float, y1: float) -> float:
    if x1 == x0:
        return y0
    return y0 + (y1 - y0) * (x - x0) / (x1 - x0)


def estimate_power(n_valid: int, n_items_valid: int,
                    pct: float = 0.20,
                    table: Optional[Dict] = None) -> Optional[float]:
    """Bir sınavın parametrelerine göre K1 gücü tahmini.

    Girdi:
        n_valid: geçerli öğrenci sayısı (excluded hariç)
        n_items_valid: geçerli madde sayısı (ölü madde eleme sonrası)
        pct: kopya senaryosu (varsayılan %20). Kalibrasyon noktaları
             {.10, .20, .40}; ara değerler için en yakın noktaya sabitlenir.

    Doner: [0, 1] arasında K1 gücü tahmini, ya da None (tablonun tamamen
           dışında).

    Yontem: n × k üzerinde bilineer interpolasyon; pct için en yakın
    kalibrasyon noktası (0.10/0.20/0.40). Sınırlar dışında en yakın
    kalibrasyon noktasına sabitlenir (extrapolasyon yok).
    """
    tbl = table if table is not None else _load_power_table()

    # pct: en yakın kalibrasyon noktasına sabitle
    pct_nearest = min(SIM_PCT_GRID, key=lambda p: abs(p - pct))

    n_lo, n_hi = _nearest(n_valid, SIM_N_GRID)
    k_lo, k_hi = _nearest(n_items_valid, SIM_K_GRID)

    # 4 köşe değer
    corners = {}
    for nn in (n_lo, n_hi):
        for kk in (k_lo, k_hi):
            v = tbl.get((nn, kk, pct_nearest))
            if v is None:
                return None
            corners[(nn, kk)] = v

    # k boyutunda önce interpolate, sonra n
    y_lo_k = _lin_interp(n_items_valid, k_lo, k_hi,
                            corners[(n_lo, k_lo)], corners[(n_lo, k_hi)])
    y_hi_k = _lin_interp(n_items_valid, k_lo, k_hi,
                            corners[(n_hi, k_lo)], corners[(n_hi, k_hi)])
    return _lin_interp(n_valid, n_lo, n_hi, y_lo_k, y_hi_k)


def estimate_power_scenarios(n_valid: int, n_items_valid: int
                                ) -> Dict[float, Optional[float]]:
    """3 senaryolu tahmin: {.10: ..., .20: ..., .40: ...}."""
    return {pct: estimate_power(n_valid, n_items_valid, pct)
             for pct in SIM_PCT_GRID}


def sensitivity_message(n_valid: int, n_items_valid: int) -> str:
    """Kullanicinin ekraninda gorunecek insan-okur duyarlilik metni."""
    scen = estimate_power_scenarios(n_valid, n_items_valid)
    if all(v is None for v in scen.values()):
        return ""
    parts = []
    for pct, p in scen.items():
        if p is None:
            continue
        parts.append(f"maddelerin %{int(pct*100)}'i kopya: ~%{int(p*100)}")
    if not parts:
        return ""
    return (f"Bu sinavin kosullarinda ({n_items_valid} gecerli madde, "
             f"{n_valid} ogrenci), K1 indeksi ile tespit olasiligi "
             f"yaklasik — " + "; ".join(parts) +
             ". Kaynak: simulation/FINDINGS.md §0.")


__all__ = [
    "estimate_power",
    "estimate_power_scenarios",
    "sensitivity_message",
    "SIM_N_GRID", "SIM_K_GRID", "SIM_PCT_GRID",
]
