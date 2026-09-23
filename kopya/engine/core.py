"""
Cheating Core — Veri Modeli + Kanonik Donusum
=============================================
Spec: cheating/claude_code_prompt_kopya_modulu.md §3

Veri modeli
-----------
- ExamData: girdinin degismez (frozen) konteyner. Numpy dizileri int8.
- IndexValue: bir indeksin cikti sozlugu (deger + p_raw + p_adj + status).
- PairResult: bir yonlu cift icin tum indekslerin sonucu.

Kanonik donusum
---------------
Ogrenci yanitlari pozisyon uzayinda saklanir (kitapcigin i. sirasindaki
soruya verilen cevap). Kanonik uzaya cevirme:

    responses_canonical[s, permutation[booklet[s], p]] = responses[s, p]

Ters donusum de mumkun. Property test: iki donusum birbirinin tersi.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Literal, Optional

import numpy as np


IndexStatus = Literal["OK", "WEAK_EVIDENCE", "NOT_COMPUTABLE", "DESCRIPTIVE_ONLY"]
# DESCRIPTIVE_ONLY: indeks hesaplanır ve değer raporlanır, ancak karar
# katmanında (kırmızı işaretleme, FDR düzeltmesi) kullanılmaz. Örnek:
# K empirical küçük c' subgroup'ta ayrık dağılım nedeniyle α = .01 için
# çok liberal (empirik α ≈ 0.15-0.30, uniformity baseline'inda belgelendi).


@dataclass(frozen=True)
class IndexValue:
    """Tek bir indeks icin cikti.

    NOT_COMPUTABLE ise `value=None` + reason doldurulur; NaN/0 dondurulmez.

    diagnostics: opsiyonel yapisal ek bilgi (ornegin G² model uyum degeri,
    p-degeri, subgroup sayisi). NOT_COMPUTABLE olsa da doldurulabilir —
    kapinin neden kapandigini gormek icin.
    """
    value: Optional[float]
    p_raw: Optional[float]
    p_adjusted: Optional[float]
    status: IndexStatus
    reason: Optional[str] = None
    calibrated: bool = True
    diagnostics: Optional[Dict[str, float]] = None


@dataclass(frozen=True)
class PairResult:
    """Yonlu cift (copier -> source) icin tum indeksler + tanimlayicilar.

    tier: "primary" (komsu VEYA kismi kapsam VEYA cakisma; karar
    katmani) veya "secondary" (komsu degil; sadece tanimlayici).
    is_neighbor: Moore komsuluk sonucu (None: koordinat cozulemedi ya
    da filtre pasif).
    """
    copier_id: str
    source_id: str
    same_booklet: bool
    indices: Dict[str, IndexValue] = field(default_factory=dict)
    descriptive: Dict[str, float] = field(default_factory=dict)
    n_used: int = 0
    tier: str = "primary"  # "primary" | "secondary"
    is_neighbor: Optional[bool] = None


@dataclass(frozen=True)
class ExamData:
    """Kopya analizinin girdi konteyneri.

    Attributes
    ----------
    responses : np.ndarray (n_students, n_positions), int8
        1..K = isaretlenen secenek, 0 = bos, -1 = coklu/okunamadi.
        Pozisyon uzayinda saklanir (kitapciktaki sıra).
    key : np.ndarray (n_canonical_items,), int8, 1..K
        Kanonik uzayda dogru secenekler.
    booklet : np.ndarray (n_students,), int
        Ogrencinin girdigi kitapcik index'i (0..n_booklets-1).
    permutation : np.ndarray (n_booklets, n_positions), int
        permutation[b, p] = kitapcik b'nin p. pozisyonundaki kanonik madde.
    student_id : np.ndarray (n_students,), object (str)
    n_options : int
        Toplam secenek sayisi K (ornek: 5 => A,B,C,D,E).
    seat_code : Optional np.ndarray (n_students,), object (str)
    hall : Optional np.ndarray (n_students,), object (str)
    proctor_verified : Optional np.ndarray (n_students,), bool
    excluded : Optional np.ndarray (n_students,), bool
    """
    responses: np.ndarray
    key: np.ndarray
    booklet: np.ndarray
    permutation: np.ndarray
    student_id: np.ndarray
    n_options: int
    seat_code: Optional[np.ndarray] = None
    hall: Optional[np.ndarray] = None
    proctor_verified: Optional[np.ndarray] = None
    excluded: Optional[np.ndarray] = None


# ── Validation ────────────────────────────────────────────

def validate_exam_data(data: ExamData) -> None:
    """Sekil ve tur invariantlarini dogrula. Yanlissa ValueError."""
    R = data.responses
    if R.ndim != 2:
        raise ValueError(f"responses 2D olmali, ndim={R.ndim}")
    n_students, n_positions = R.shape

    if data.key.ndim != 1:
        raise ValueError("key 1D olmali")
    n_canonical = data.key.shape[0]
    if n_canonical != n_positions:
        raise ValueError(
            f"key uzunlugu ({n_canonical}) responses sutunundan ({n_positions}) farkli"
        )

    if data.booklet.shape != (n_students,):
        raise ValueError(
            f"booklet shape {data.booklet.shape} != ({n_students},)"
        )
    if data.booklet.min() < 0:
        raise ValueError("booklet index negatif olamaz")
    n_booklets = int(data.booklet.max()) + 1

    if data.permutation.shape != (n_booklets, n_positions):
        raise ValueError(
            f"permutation shape {data.permutation.shape} != "
            f"({n_booklets}, {n_positions})"
        )
    # Her satir 0..n_positions-1 permutasyonu mu?
    expected = np.arange(n_positions)
    for b in range(n_booklets):
        row = np.sort(data.permutation[b])
        if not np.array_equal(row, expected):
            raise ValueError(
                f"permutation[{b}] tam permutasyon degil"
            )

    if data.student_id.shape != (n_students,):
        raise ValueError("student_id shape mismatch")

    if data.n_options < 2:
        raise ValueError(f"n_options >= 2 olmali, {data.n_options}")

    # Response degerleri: -1, 0, 1..K
    vmin, vmax = int(R.min()), int(R.max())
    if vmin < -1:
        raise ValueError(f"responses min {vmin} < -1")
    if vmax > data.n_options:
        raise ValueError(f"responses max {vmax} > n_options {data.n_options}")

    # Key degerleri: 1..K
    if data.key.min() < 1 or data.key.max() > data.n_options:
        raise ValueError(
            f"key degerleri 1..{data.n_options} disinda: [{data.key.min()},{data.key.max()}]"
        )

    for name, arr in [("seat_code", data.seat_code),
                       ("hall", data.hall),
                       ("proctor_verified", data.proctor_verified),
                       ("excluded", data.excluded)]:
        if arr is not None and arr.shape != (n_students,):
            raise ValueError(f"{name} shape {arr.shape} != ({n_students},)")


# ── Kanonik ↔ Pozisyon donusumu ──────────────────────────

def to_canonical_matrix(responses: np.ndarray,
                          booklet: np.ndarray,
                          permutation: np.ndarray) -> np.ndarray:
    """responses[s, p] -> canonical[s, permutation[booklet[s], p]]

    Ayni tip ve seklinde ndarray doner. Bos/coklu/gecerli tum degerler
    tasinir (secime dokunulmaz).
    """
    if responses.ndim != 2:
        raise ValueError("responses 2D olmali")
    n_students, n_positions = responses.shape
    if permutation.ndim != 2 or permutation.shape[1] != n_positions:
        raise ValueError("permutation shape uyumsuz")
    if booklet.shape != (n_students,):
        raise ValueError("booklet shape uyumsuz")

    out = np.empty_like(responses)
    # Vektorlestirilmis: her satir icin ilgili kitapcigin permutasyonuyla
    # yeniden siralar. permutation[booklet[s]] indeksleme dizisidir.
    perms_per_student = permutation[booklet]  # (n_students, n_positions)
    # canonical[s, perms_per_student[s, p]] = responses[s, p]
    # Yani inverse indexing: out[s, perms[s, p]] = responses[s, p]
    rows = np.arange(n_students)[:, None]
    out[rows, perms_per_student] = responses
    return out


