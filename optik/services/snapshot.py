"""
Snapshot servisi: onay anında batch kayıtlarının değişmez kopyası.

Kaynak: omr_analysis/service_snapshot.py

Farklar:
- Snapshot'lar dizin yerine `OptikSnapshot` satırlarında tutulur
  (store.create_snapshot_row / list_snapshot_rows / get_snapshot_row).
- Kaynaktaki listeleme/geri yükleme/silme fonksiyonlarının arayüzü yoktu;
  alınmadı.
- Düzeltme: kaynak yalnızca `status == "ACTIVE"` kayıtları kopyalıyordu ama
  OMR kayıtlarında status alanı hiç yok, bu yüzden snapshot'lar boştu.
  Artık status'u olmayan kayıtlar ACTIVE sayılır; yalnızca açıkça başka bir
  status taşıyan kayıtlar (örn. "UPLOADED") atlanır.
- `created_by`: User nesnesi veya id; id saklanır.
- `get_snapshot` bulunamazsa `store.NotFound` yükseltir.
"""
import logging
from typing import Any, Dict, List

from django.db import transaction

from optik import store
from optik.services import core as service
from optik.services import override as override_service
from optik.store import now_iso

logger = logging.getLogger(__name__)


def _version_number(version: str) -> int:
    v = str(version or "")
    return int(v[1:]) if v.startswith("v") and v[1:].isdigit() else 0


def get_next_version(batch_id: str) -> int:
    """Bir sonraki version numarasını getir."""
    versions = [_version_number(r.version) for r in store.list_snapshot_rows(batch_id)]
    return max(versions, default=0) + 1


# Geri yüklemede eski kayıttan taşınan alanlar (kaynakta kayboluyordu)
_KEEP_ON_RESTORE = ("image_path", "overlay_path", "processed_at", "omr_confidence")


def _is_active(record: Dict[str, Any]) -> bool:
    return (record.get("status") or "ACTIVE") == "ACTIVE"


def create_snapshot(batch_id: str, created_by: Any, reason: str = "") -> str:
    """
    Snapshot oluştur.

    Args:
        created_by: Snapshot'ı oluşturan kullanıcı (User veya id)
        reason: Neden (approval, correction, ...)

    Returns:
        Snapshot version (örn: "v1")
    """
    snapshot_records: List[Dict[str, Any]] = []
    active_ids: List[str] = []

    for record in store.list_records(batch_id):
        try:
            if not _is_active(record):
                continue

            record_id = record.get("record_id")
            effective = override_service.effective_from_record(record)

            snapshot_records.append({
                "record_id": record_id,
                "original_filename": record.get("original_filename", ""),
                "status": "ACTIVE",
                "effective": {
                    "student_no": effective["effective"].get("student_no", ""),
                    "class_code": effective["effective"].get("class_code", ""),
                    "booklet": effective["effective"].get("booklet", ""),
                    "seating": effective["effective"].get("seating", {}),
                    "answers": effective["effective"].get("answers", [])
                },
                "has_overrides": effective["has_overrides"],
                "override_fields": list(effective["overrides"].keys()) if effective["overrides"] else []
            })
            active_ids.append(record_id)
        except Exception as e:
            logger.warning("Snapshot kayıt hatası: %s - %s", record.get("record_id"), e)

    with transaction.atomic():
        next_ver = get_next_version(batch_id)
        metadata = {
            "snapshot_version": next_ver,
            "batch_id": batch_id,
            "created_at": now_iso(),
            "created_by": service.user_id(created_by),
            "reason": reason or "Batch approved",
            "record_count": len(active_ids),
            "record_ids": active_ids
        }
        store.create_snapshot_row(batch_id, f"v{next_ver}", metadata, snapshot_records)

    return f"v{next_ver}"


def get_snapshot(batch_id: str, version: str) -> Dict[str, Any]:
    """
    Belirli bir snapshot'ı getir.

    Returns:
        {"metadata": {...}, "records": [...]}
    """
    row = store.get_snapshot_row(batch_id, version)
    return {"metadata": dict(row.metadata or {}), "records": list(row.records or [])}


