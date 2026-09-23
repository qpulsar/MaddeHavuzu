"""
Kopya analizi hesap yönetimi
============================
Kaynak (cheating/routes.py) sonuçları süreç belleğinde (LRU) tutuyordu; sunucu
yeniden başlayınca kayboluyordu, Excel yüklemeleri de bellekte olmadığında
KeyError veriyordu. Burada:

- Girdi: optik batch (kopya.adapter) veya Excel yüklemesi (KopyaUpload dosyası
  + read_excel) → ExamData.
- Anahtar: (source_id, alpha, input_hash). Sonuç `KopyaAnalysis` tablosunda
  pickle olarak saklanır; yeniden başlatmada korunur.
- Eksikse analyze_exam modül düzeyindeki ThreadPoolExecutor'da çalışır
  (settings.KOPYA_WORKERS, varsayılan 2). Aynı (source_id, alpha) için eş
  zamanlı istekler tek hesapta birleştirilir (kaynaktaki gibi).
- settings.KOPYA_SYNC = True ise hesap istek içinde, eşzamanlı yapılır
  (testler için).
"""

from __future__ import annotations

import concurrent.futures
import logging
import pickle
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

from django.conf import settings
from django.db import IntegrityError, close_old_connections
from django.utils.dateparse import parse_datetime

from kopya.engine import analyze_exam
from kopya.engine._pairwise import _input_hash
from kopya.models import KopyaAnalysis, KopyaUpload
from optik.models import OptikBatch

logger = logging.getLogger(__name__)

DEFAULT_ALPHA = 0.01


class SourceError(Exception):
    """Analiz girdisi yüklenemedi (kullanıcıya gösterilecek Türkçe mesaj)."""


# ── Girdi yükleme ─────────────────────────────────────────────────────────

def is_excel_source(source_id: str) -> bool:
    return str(source_id).startswith("xl_")


def load_excel_upload(upload: KopyaUpload):
    """KopyaUpload dosyasını okuyup (ExamData, meta) döndür."""
    from kopya.engine.excel_upload import read_excel
    try:
        with upload.file.open("rb") as f:
            contents = f.read()
    except (OSError, ValueError) as e:
        raise SourceError(
            f"Excel dosyası okunamadı ({upload.original_filename}): {e}. "
            f"Dosyayı yeniden yükleyin.")
    r = read_excel(contents)
    if not r.validation.ok:
        raise SourceError(
            "Kayıtlı Excel dosyası okunamadı: "
            + "; ".join(r.validation.blocking_errors))
    return r.exam_data, dict(upload.meta or {})


def load_source(source_id: str):
    """source_id → (ExamData, meta). Yetki kontrolü çağıran view'dadır."""
    if is_excel_source(source_id):
        upload = KopyaUpload.objects.filter(upload_id=source_id).first()
        if upload is None:
            raise SourceError(
                f"Excel yüklemesi {source_id} bulunamadı. Dosyayı yeniden yükleyin.")
        return load_excel_upload(upload)
    from kopya.adapter import AdapterError, batch_to_exam_data
    try:
        return batch_to_exam_data(source_id)
    except AdapterError as e:
        raise SourceError(str(e))


# ── Kalıcı sonuç deposu ───────────────────────────────────────────────────

# Aynı sonucun her sayfa açılışında yeniden unpickle edilmemesi için küçük
# süreç içi LRU (kalıcı değil; kalıcı kaynak veritabanıdır).
# Anahtar: satır kimliği + hesap zamanı (pk tek başına yeniden kullanılabilir).
_RESULT_LRU: "OrderedDict[tuple, Any]" = OrderedDict()
_RESULT_LRU_MAX = 8
_lru_lock = threading.Lock()


def _unpickle(row: KopyaAnalysis):
    key = (row.pk, row.source_id, row.alpha, row.input_hash,
           row.computed_at.isoformat() if row.computed_at else "")
    with _lru_lock:
        if key in _RESULT_LRU:
            _RESULT_LRU.move_to_end(key)
            return _RESULT_LRU[key]
    result = pickle.loads(bytes(row.result))
    with _lru_lock:
        _RESULT_LRU[key] = result
        while len(_RESULT_LRU) > _RESULT_LRU_MAX:
            _RESULT_LRU.popitem(last=False)
    return result


def get_stored(source_id: str, alpha: float, input_hash: str):
    """Veritabanındaki sonucu döndür (yoksa None)."""
    row = (KopyaAnalysis.objects
           .filter(source_id=source_id, alpha=float(alpha), input_hash=input_hash)
           .first())
    return _unpickle(row) if row is not None else None


def compute_and_store(source_id: str, alpha: float, data):
    """analyze_exam'i eşzamanlı çalıştır ve sonucu kaydet. Sonucu döndürür."""
    input_hash = _input_hash(data)
    t0 = time.time()
    result = analyze_exam(data, alpha=alpha)
    duration = time.time() - t0
    try:
        KopyaAnalysis.objects.update_or_create(
            source_id=source_id, alpha=float(alpha), input_hash=input_hash,
            defaults={"result": pickle.dumps(result, protocol=pickle.HIGHEST_PROTOCOL),
                      "duration_seconds": duration},
        )
    except IntegrityError:
        # Eş zamanlı başka bir süreç aynı anahtarı yazdı — sonuç aynıdır.
        pass
    # Aynı kaynağın eski verilerle (farklı girdi özeti) hesaplanmış sonuçları artık geçersiz
    KopyaAnalysis.objects.filter(source_id=source_id).exclude(input_hash=input_hash).delete()
    return result


# ── Arka plan hesap yönetimi ──────────────────────────────────────────────

_executor: Optional[concurrent.futures.ThreadPoolExecutor] = None
_executor_lock = threading.Lock()
_in_progress_lock = threading.Lock()
_IN_PROGRESS: Dict[str, concurrent.futures.Future] = {}
_STARTED_AT: Dict[str, float] = {}
# Son başarısız hesaplar: prog_key → (input_hash, mesaj). Sayfa yenilemesinde
# sonsuz "hesaplanıyor" döngüsü yerine hata gösterilir; bir kez gösterilince
# silinir (sonraki istek yeniden dener).
_FAILED: Dict[str, Tuple[str, str]] = {}


def _get_executor() -> concurrent.futures.ThreadPoolExecutor:
    global _executor
    with _executor_lock:
        if _executor is None:
            workers = int(getattr(settings, "KOPYA_WORKERS", 2) or 2)
            _executor = concurrent.futures.ThreadPoolExecutor(
                max_workers=max(1, workers), thread_name_prefix="kopya-analysis")
        return _executor


def _prog_key(source_id: str, alpha: float) -> str:
    return f"{source_id}::{float(alpha):.6g}"


def _worker(source_id: str, alpha: float, data, prog_key: str):
    close_old_connections()
    try:
        return compute_and_store(source_id, alpha, data)
    except Exception as e:  # noqa: BLE001
        logger.exception("Kopya analizi başarısız: %s", prog_key)
        with _in_progress_lock:
            _FAILED[prog_key] = (_input_hash(data), f"Analiz hesaplanamadı: {e}")
        raise
    finally:
        with _in_progress_lock:
            _IN_PROGRESS.pop(prog_key, None)
            _STARTED_AT.pop(prog_key, None)
        close_old_connections()


def start_analysis(source_id: str, alpha: float, data) -> concurrent.futures.Future:
    """Devam eden hesap varsa onu döndür; yoksa yeni hesap başlat."""
    key = _prog_key(source_id, alpha)
    with _in_progress_lock:
        fut = _IN_PROGRESS.get(key)
        if fut is not None and not fut.done():
            return fut
        _FAILED.pop(key, None)
        _STARTED_AT[key] = time.time()
        fut = _get_executor().submit(_worker, source_id, alpha, data, key)
        _IN_PROGRESS[key] = fut
    return fut


def is_in_progress(source_id: str, alpha: float = DEFAULT_ALPHA) -> bool:
    key = _prog_key(source_id, alpha)
    with _in_progress_lock:
        fut = _IN_PROGRESS.get(key)
        return fut is not None and not fut.done()


def sync_mode() -> bool:
    return bool(getattr(settings, "KOPYA_SYNC", False))


@dataclass
class Outcome:
    """get_or_compute sonucu. result None ise hesap sürüyor (elapsed_s)."""
    result: Any
    data: Any
    meta: Dict[str, Any]
    elapsed_s: float = 0.0

    @property
    def ready(self) -> bool:
        return self.result is not None


def get_or_compute(source_id: str, alpha: float, timeout_s: float = 0.15) -> Outcome:
    """Kayıtlı sonuç varsa hemen döndür; yoksa hesabı başlat/bul ve kısa süre
    bekle. Bitmezse Outcome(result=None, elapsed_s=...) — "hesaplanıyor" sayfası.

    SourceError: girdi yüklenemedi veya hesap başarısız oldu.
    """
    data, meta = load_source(source_id)
    input_hash = _input_hash(data)
    result = get_stored(source_id, alpha, input_hash)
    if result is not None:
        return Outcome(result, data, meta)

    if sync_mode():
        try:
            result = compute_and_store(source_id, alpha, data)
        except Exception as e:  # noqa: BLE001
            raise SourceError(f"Analiz hesaplanamadı: {e}")
        return Outcome(result, data, meta)

    key = _prog_key(source_id, alpha)
    with _in_progress_lock:
        failed = _FAILED.get(key)
        running = key in _IN_PROGRESS and not _IN_PROGRESS[key].done()
        if failed and failed[0] == input_hash and not running:
            _FAILED.pop(key, None)
            raise SourceError(failed[1])

    fut = start_analysis(source_id, alpha, data)
    try:
        result = fut.result(timeout=timeout_s)
        return Outcome(result, data, meta)
    except concurrent.futures.TimeoutError:
        with _in_progress_lock:
            started = _STARTED_AT.get(key, time.time())
        return Outcome(None, data, meta, elapsed_s=time.time() - started)
    except Exception as e:  # noqa: BLE001
        with _in_progress_lock:
            _FAILED.pop(key, None)
        raise SourceError(f"Analiz hesaplanamadı: {e}")


def trigger(source_id: str, alpha: float, data) -> None:
    """Yükleme sonrası hesabı başlat (senkron modda hemen hesapla)."""
    if get_stored(source_id, alpha, _input_hash(data)) is not None:
        return
    if sync_mode():
        compute_and_store(source_id, alpha, data)
    else:
        start_analysis(source_id, alpha, data)


def analysis_states(source_ids, alpha: float = DEFAULT_ALPHA) -> Dict[str, str]:
    """Liste sayfası için durum: 'done' | 'running' | 'none'.

    'done': kayıtlı sonuç var ve (optik batch'lerde) son puanlamadan sonra
    hesaplanmış. Yeniden puanlanan batch "Hesapla" durumuna döner.
    """
    ids = list(source_ids)
    latest: Dict[str, Any] = {}
    for sid, computed_at in (KopyaAnalysis.objects
                             .filter(source_id__in=ids, alpha=float(alpha))
                             .values_list("source_id", "computed_at")):
        if sid not in latest or computed_at > latest[sid]:
            latest[sid] = computed_at
    scored_at = dict(OptikBatch.objects.filter(batch_id__in=list(latest))
                     .values_list("batch_id", "scores__scored_at"))
    done = set()
    for sid, computed_at in latest.items():
        stamp = parse_datetime(scored_at[sid]) if scored_at.get(sid) else None
        if stamp is None or computed_at >= stamp:
            done.add(sid)
    out: Dict[str, str] = {}
    for sid in ids:
        if sid in done:
            out[sid] = "done"
        elif is_in_progress(sid, alpha):
            out[sid] = "running"
        else:
            out[sid] = "none"
    return out
