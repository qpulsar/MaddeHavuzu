"""
Oturma Duzeni ve Komsuluk (SIM-13)
====================================
Optik form oturma kodu (A1, B2, ..., H9) + salon bilgisi uzerinden
**Moore komsulugu** (yatay, dikey, caprazlar — 8 komsu) hesaplar.

Iki katmanli sistem
-------------------
- Birincil katman: komsu ciftler + kismi kapsam kuralindan gelenler
  → tam indeks + FDR + gosterge sayimi (karar katmani)
- Ikincil katman: komsuluk disi ciftler → yalniz tanimlayici siralama
  (p-degeri yok, FDR yok)

Kismi kapsam kurali
-------------------
Oturma kodu olmayan ogrencilerin dahil oldugu ciftler komsuluk karari
verilemediginden **birincil katmana** alinir (muhafazakar taraf).

Kapsam esigi
------------
Sinifin kapsam orani < DEFAULT_COVERAGE_THRESHOLD (%80) ise filtre
otomatik devre disi — tum ciftler birincil katmanda, mevcut davranis.

Not
---
Bu filtrenin guc uzerindeki etkisi simulasyonda olculmedi (oturma bilgisi
kapsam disi idi). Filtre fiziksel firsat mantigina dayanir; ampirik guc
kazanci bu calismada olculmemistir. Bkz. README.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np


DEFAULT_COVERAGE_THRESHOLD = 0.80  # Yapilandirilabilir — filtre için minimum
_LETTER_TO_ROW: Dict[str, int] = {chr(ord("A") + i): i + 1 for i in range(26)}


def parse_seat_label(code: Optional[str]) -> Optional[Tuple[int, int]]:
    """"A1" → (1, 1);  "C4" → (3, 4);  "H9" → (8, 9).

    Kabul edilen format: bir buyuk-harf satir + bir veya daha cok
    rakamli koltuk numarasi ("A1", "AA10" degil). Kucuk harf buyuk
    harfe cevirilir.

    None doner: kod bos, format tanimsiz, harf 26 disi.
    """
    if not code:
        return None
    s = str(code).strip().upper()
    if len(s) < 2:
        return None
    letter = s[0]
    rest = s[1:]
    if letter not in _LETTER_TO_ROW:
        return None
    if not rest.isdigit():
        return None
    seat_no = int(rest)
    if seat_no < 1:
        return None
    return (_LETTER_TO_ROW[letter], seat_no)


def are_moore_neighbors(
    seat_a: Optional[Tuple[int, int]],
    seat_b: Optional[Tuple[int, int]],
    hall_a: Optional[str] = None,
    hall_b: Optional[str] = None,
) -> Optional[bool]:
    """Moore komsuluğu (8 komsu). Doner:
      True → komsu
      False → aynı salonda ama komsu degil, veya farkli salon
      None → koordinat cozulemedi (bilinmiyor)
    """
    if seat_a is None or seat_b is None:
        return None
    # Farkli salon → komsu degil (kesin False)
    if hall_a is not None and hall_b is not None and hall_a != hall_b:
        return False
    r1, c1 = seat_a
    r2, c2 = seat_b
    if r1 == r2 and c1 == c2:
        return False  # ayni koltuk — cakisma; komsu degil (ayri hata olarak isaretlenir)
    return (abs(r1 - r2) <= 1) and (abs(c1 - c2) <= 1)


@dataclass(frozen=True)
class SeatingReport:
    """Oturma verisi kalite raporu (spec §4)."""
    n_total: int
    n_with_seat: int
    coverage_ratio: float
    n_parse_errors: int
    parse_error_examples: List[str]
    seat_collisions: List[Tuple[str, str, str]]  # (student_a, student_b, seat)
    hall_available: bool
    n_halls: int
    filter_active: bool
    reason: str


def build_seating_report(
    student_ids: np.ndarray,
    seat_codes: Optional[np.ndarray],
    halls: Optional[np.ndarray] = None,
    coverage_threshold: float = DEFAULT_COVERAGE_THRESHOLD,
) -> SeatingReport:
    """Kalite kontrol + filtre etkin mi karari.

    coverage_ratio < coverage_threshold ise filter_active = False:
    tum ciftler birincil katmanda, mevcut davranis.
    """
    n = len(student_ids)
    if seat_codes is None:
        return SeatingReport(
            n_total=n, n_with_seat=0, coverage_ratio=0.0,
            n_parse_errors=0, parse_error_examples=[],
            seat_collisions=[], hall_available=False, n_halls=0,
            filter_active=False,
            reason="Oturma kodu yok → tek katman (mevcut davranis)",
        )
    parsed: List[Optional[Tuple[int, int]]] = []
    parse_errors: List[str] = []
    for i, code in enumerate(seat_codes):
        s = (str(code).strip() if code is not None else "")
        if not s:
            parsed.append(None)
            continue
        p = parse_seat_label(s)
        if p is None:
            parsed.append(None)
            if len(parse_errors) < 10:
                parse_errors.append(f"{student_ids[i]}: '{s}'")
        else:
            parsed.append(p)
    n_with_seat = sum(1 for p in parsed if p is not None)
    coverage = n_with_seat / n if n > 0 else 0.0

    # Cakisma tespiti — aynı (hall, seat) çoklu öğrenci
    seat_map: Dict[Tuple[Optional[str], Tuple[int, int]], List[int]] = {}
    for i, p in enumerate(parsed):
        if p is None:
            continue
        h = None
        if halls is not None:
            h = str(halls[i]) if halls[i] is not None else None
        key = (h, p)
        seat_map.setdefault(key, []).append(i)
    collisions: List[Tuple[str, str, str]] = []
    for (h, seat), members in seat_map.items():
        if len(members) < 2:
            continue
        seat_str = f"{chr(ord('A') + seat[0] - 1)}{seat[1]}"
        for i in range(len(members)):
            for j in range(i + 1, len(members)):
                collisions.append((
                    str(student_ids[members[i]]),
                    str(student_ids[members[j]]),
                    (f"{h}::{seat_str}" if h else seat_str),
                ))

    hall_available = halls is not None and any(
        (halls[i] is not None and str(halls[i]).strip())
        for i in range(n)
    )
    n_halls = 0
    if hall_available:
        n_halls = len(set(
            str(halls[i]) for i in range(n)
            if halls[i] is not None and str(halls[i]).strip()
        ))

    if coverage < coverage_threshold:
        filter_active = False
        reason = (f"Kapsam orani {coverage:.1%} < esigin altinda "
                   f"({coverage_threshold:.0%}) → filtre devre disi, "
                   f"tum ciftler birincil katmanda")
    else:
        filter_active = True
        reason = (f"Kapsam orani {coverage:.1%} yeterli → iki katmanli "
                   f"analiz aktif")

    return SeatingReport(
        n_total=n, n_with_seat=n_with_seat, coverage_ratio=coverage,
        n_parse_errors=len(parse_errors),
        parse_error_examples=parse_errors,
        seat_collisions=collisions,
        hall_available=hall_available,
        n_halls=n_halls,
        filter_active=filter_active,
        reason=reason,
    )


__all__ = [
    "DEFAULT_COVERAGE_THRESHOLD",
    "parse_seat_label",
    "are_moore_neighbors",
    "SeatingReport",
    "build_seating_report",
]
