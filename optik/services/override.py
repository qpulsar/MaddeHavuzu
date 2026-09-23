"""
Override servisi: OMR hatalarının elle düzeltilmesi.

Kaynak: omr_analysis/service_override.py

Farklar: kayıtlar `optik.store` üzerinden okunur/yazılır; bulunamayan kayıt
için `FileNotFoundError` yerine `store.NotFound` yükselir. `user_id`
parametresi User nesnesi veya id alır, id saklanır.
"""
from typing import Any, Dict

from optik import store


def apply_overrides(raw_result: Dict[str, Any], overrides: Dict[str, Any]) -> Dict[str, Any]:
    """Override'ları raw result'a uygula."""
    effective = raw_result.copy()
    for field, value in overrides.items():
        effective[field] = value
    return effective


def effective_from_record(record: Dict[str, Any]) -> Dict[str, Any]:
    """Kayıt dict'inden raw/overrides/effective üret."""
    raw = {
        "student_no": record.get("student_no", ""),
        "class_code": record.get("class_code", ""),
        "booklet": record.get("booklet", ""),
        "answers": record.get("answers", []),
        "seating": record.get("seating", {})
    }

    overrides = record.get("overrides", {}) or {}
    return {
        "raw": raw,
        "overrides": overrides,
        "effective": apply_overrides(raw, overrides),
        "has_overrides": bool(overrides)
    }


def get_effective_result(batch_id: str, record_id: str) -> Dict[str, Any]:
    """Effective result getir (raw + overrides). Kayıt yoksa NotFound."""
    return effective_from_record(store.get_record(batch_id, record_id))
