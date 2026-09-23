"""
Arka plan form işleme (çok sayıda formun OMR okuması).

Kaynak: omr_analysis/service_background.py

Farklar:
- İş, modül düzeyinde bir `ThreadPoolExecutor(max_workers=settings.OPTIK_WORKERS)`
  üzerinde çalışır; `start_processing()` işi kuyruğa atıp hemen döner.
- İlerleme `store.update_batch_fields` (satır kilitli) ile yazılır; `progress`
  dict şeması ve durum değerleri kaynakla aynıdır.
- `process_forms_background` senkron da çağrılabilir (testler böyle çağırır).
- Batch klasörü dışındaki dosyalar okunmadan önce batch uploads klasörüne
  kopyalanır; kayıttaki `image_path`/`overlay_path` hep oradadır.
"""
import logging
import os
import shutil
import threading
import traceback
import uuid
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any, Dict, List, Optional

from django.conf import settings
from django.db import close_old_connections, connection

from optik import store
from optik.services import core as service
from optik.services import omr as omr_service
from optik.store import now_iso

logger = logging.getLogger(__name__)

ANSWER_KEY_STUDENT_NO = "111111111111"

_executor: Optional[ThreadPoolExecutor] = None
_executor_lock = threading.Lock()

# Per-batch lock: aynı batch'in progress oku+birleştir+yaz adımlarını serileştir
_batch_locks: Dict[str, threading.Lock] = {}
_batch_locks_lock = threading.Lock()


def _get_executor() -> ThreadPoolExecutor:
    global _executor
    with _executor_lock:
        if _executor is None:
            _executor = ThreadPoolExecutor(
                max_workers=max(1, int(getattr(settings, "OPTIK_WORKERS", 2))),
                thread_name_prefix="optik",
            )
        return _executor


def _get_batch_lock(batch_id: str) -> threading.Lock:
    with _batch_locks_lock:
        if batch_id not in _batch_locks:
            _batch_locks[batch_id] = threading.Lock()
        return _batch_locks[batch_id]


def _close_old_connections() -> None:
    # Senkron çağrıda (istek/test transaction'ı içinde) bağlantıya dokunma
    if not connection.in_atomic_block:
        close_old_connections()


def start_processing(batch_id: str, file_paths: List[str], user: Any = None) -> Future:
    """İşlemeyi arka planda başlat ve hemen dön (Future döner)."""
    store.update_batch_fields(
        batch_id,
        status="PROCESSING",
        processing_started_by=service.user_id(user),
        progress={
            "total_files": len(file_paths),
            "processed": 0,
            "success": 0,
            "failed": 0,
            "progress_percentage": 0,
            "started_at": now_iso(),
        },
    )
    return _get_executor().submit(process_forms_background, batch_id, list(file_paths))


def _ensure_in_upload_dir(batch_id: str, file_path: str) -> str:
    """Dosya batch klasöründe değilse uploads klasörüne kopyala."""
    if store.is_inside_batch_dir(batch_id, file_path):
        return file_path
    upload_dir = store.get_upload_dir(batch_id)
    target = os.path.join(upload_dir, os.path.basename(file_path))
    if os.path.exists(target):
        name, ext = os.path.splitext(os.path.basename(file_path))
        target = os.path.join(upload_dir, f"{name}_{uuid.uuid4().hex[:6]}{ext}")
    shutil.copy2(file_path, target)
    return target


def process_forms_background(
    batch_id: str,
    file_paths: List[str],
    test_id: Optional[str] = None,
) -> None:
    """
    Formları işle (arka plan iş parçacığında veya senkron).

    Args:
        batch_id: Batch ID
        file_paths: Form görüntü yolları
        test_id: Test ID (verilmezse batch'ten alınır)
    """
    _close_old_connections()
    try:
        _process(batch_id, file_paths, test_id)
    finally:
        _close_old_connections()


def _process(batch_id: str, file_paths: List[str], test_id: Optional[str]) -> None:
    try:
        if not test_id:
            test_id = service.get_batch(batch_id)["test_id"]
        test = service.get_test(test_id)
        expected_booklets = test.get("booklets", ["A"])
        # OMR sadece çoktan seçmeli (MCQ) maddeleri okur
        question_counts = test.get("question_counts", {})
        mcq_count = question_counts.get("MCQ", 0)
        num_items = mcq_count if mcq_count > 0 else test.get("num_items", 50)
        upload_dir = store.get_upload_dir(batch_id)

        update_batch_status(batch_id, "PROCESSING", {
            "total_files": len(file_paths),
            "processed": 0,
            "success": 0,
            "failed": 0,
            "started_at": now_iso()
        })
    except Exception as e:
        logger.exception("Optik batch %s başlatılamadı", batch_id)
        try:
            update_batch_status(batch_id, "FAILED", {
                "error": str(e),
                "traceback": traceback.format_exc()
            })
        except Exception:
            logger.exception("Batch %s FAILED durumu da yazılamadı", batch_id)
        return

    success_count = 0
    failed_count = 0
    errors: List[Dict[str, str]] = []
    total = len(file_paths)

    def _progress(idx: int) -> None:
        update_batch_status(batch_id, "PROCESSING", {
            "total_files": total,
            "processed": idx,
            "success": success_count,
            "failed": failed_count,
            "progress_percentage": int((idx / total) * 100) if total else 100
        })

    try:
        for idx, file_path in enumerate(file_paths, 1):
            try:
                local_path = _ensure_in_upload_dir(batch_id, file_path)
                success, record, error_msg = omr_service.process_form_image(
                    local_path, test_id, expected_booklets, num_items, overlay_dir=upload_dir
                )

                if success and record:
                    student_no = record.get("student_no", "")
                    # 111111111111 numaralı form cevap anahtarıdır
                    if student_no == ANSWER_KEY_STUDENT_NO:
                        booklet = record.get("booklet", "")
                        if not booklet or booklet not in ("A", "B", "C", "D"):
                            booklet = expected_booklets[0] if expected_booklets else "A"
                        ak_dict = {
                            f"Q{i + 1}": ans
                            for i, ans in enumerate(record.get("answers", []))
                            if ans and ans not in ("", "?", "!")
                        }
                        if ak_dict:
                            service.set_answer_key(test_id, booklet, ak_dict)
                            service.auto_set_item_points(test_id)
                            logger.info("Optik %s: cevap anahtarı kaydedildi (kitapçık %s)", batch_id, booklet)
                        success_count += 1
                    else:
                        record_id = record.get("record_id") or f"rec_{idx}"
                        store.save_record(batch_id, record_id, record)
                        success_count += 1
                else:
                    failed_count += 1
                    errors.append({
                        "file": os.path.basename(file_path),
                        "error": error_msg or "Unknown error"
                    })
            except Exception as e:
                failed_count += 1
                errors.append({"file": os.path.basename(file_path), "error": str(e)})
                logger.exception("Optik %s: %s işlenemedi", batch_id, file_path)

            _progress(idx)

        final_status = "COMPLETED" if failed_count == 0 else "COMPLETED_WITH_ERRORS"
        update_batch_status(batch_id, final_status, {
            "total_files": total,
            "processed": total,
            "success": success_count,
            "failed": failed_count,
            "progress_percentage": 100,
            "completed_at": now_iso(),
            "errors": errors if errors else None
        })

        store.update_batch_fields(batch_id, record_count=service.get_record_count(batch_id))
        logger.info("Optik %s tamamlandı: %d başarılı, %d hatalı", batch_id, success_count, failed_count)

    except Exception as e:
        logger.exception("Optik %s işlem döngüsü hatası", batch_id)
        update_batch_status(batch_id, "FAILED", {
            "total_files": total,
            "processed": success_count + failed_count,
            "success": success_count,
            "failed": failed_count,
            "error": str(e),
            "errors": errors if errors else None
        })


def update_batch_status(
    batch_id: str,
    status: str,
    progress_info: Dict[str, Any] = None
) -> None:
    """
    Batch durumunu ve progress bilgisini güncelle (progress birleştirilir).

    status: PROCESSING, COMPLETED, COMPLETED_WITH_ERRORS, FAILED
    """
    with _get_batch_lock(batch_id):
        updates: Dict[str, Any] = {"status": status, "updated_at": now_iso()}
        if progress_info:
            progress = dict(store.load_batch(batch_id).get("progress") or {})
            progress.update(progress_info)
            updates["progress"] = progress
        store.update_batch_fields(batch_id, **updates)


def get_batch_progress(batch_id: str) -> Dict[str, Any]:
    """
    Batch progress bilgisini getir.

    Returns:
        {"status", "total_files", "error", "processed", "success", "failed",
         "progress_percentage", "is_complete", "errors", "started_at", "completed_at"}
    """
    batch = service.get_batch(batch_id)

    status = batch.get("status", "CREATED")
    progress = batch.get("progress") or {}

    return {
        "status": status,
        "total_files": progress.get("total_files", 0),
        "error": progress.get("error"),
        "processed": progress.get("processed", 0),
        "success": progress.get("success", 0),
        "failed": progress.get("failed", 0),
        "progress_percentage": progress.get("progress_percentage", 0),
        "is_complete": status in ["COMPLETED", "COMPLETED_WITH_ERRORS", "FAILED"],
        "errors": progress.get("errors") or [],
        "started_at": progress.get("started_at"),
        "completed_at": progress.get("completed_at")
    }


