"""
Kopya Analizi Modulu (Cheating Analysis)
========================================
Coktan secmeli sinav yanit oruntuleri uzerinden istatistiksel kopya
gostergeleri hesaplar. **Karar destek** amaclidir; kopya karari vermez.

Kapsam (v1)
-----------
- Parametresiz esli benzerlik indeksleri: K, K1, K2, S1, S2
- Birey-uyum indeksleri: U3, H^T
- Tanimlayici olcumler
- Cok kitapcikli sinavda kanonik (A kitapcigi) uzayda karsilastirma
- FDR duzeltmesi

Kapsam disi (v1)
----------------
- MTK/IRT tabanli indeksler (omega, GBT)
- Otomatik yorum uretme
- Secenek karistirma

Referanslar
-----------
- Holland (1996) — K, K1, K2
- Sotaridona & Meijer (2002, 2003) — S1, S2
- van der Flier (1982) — U3
- Sijtsma & Meijer (1992) — H^T

Kalibrasyon ve yontem notlari: `kopya/engine/README.md`
"""

__version__ = "0.1.0"

from kopya.engine.core import (
    ExamData,
    IndexValue,
    PairResult,
    to_canonical_matrix,
    validate_exam_data,
)
from kopya.engine._pairwise import AnalysisResult, analyze_exam, bh_fdr

__all__ = [
    "ExamData",
    "IndexValue",
    "PairResult",
    "AnalysisResult",
    "analyze_exam",
    "bh_fdr",
    "to_canonical_matrix",
    "validate_exam_data",
    "__version__",
]
