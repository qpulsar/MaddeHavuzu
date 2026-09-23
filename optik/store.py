"""
Optik veri katmanı.

Kaynak modüldeki `shared.database` / `shared.paths` fonksiyonlarının Django
modelleri üzerindeki karşılığı. Servisler dict alıp verir; dict ile model
sütunları burada eşitlenir.

Dosyalar (yüklenen görüntüler, overlay'ler) MEDIA_ROOT/optik/<batch_id>/
altında tutulur ve yalnızca yetki kontrollü view'lar üzerinden sunulur.
"""
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from optik.models import OptikBatch, OptikRecord, OptikSnapshot, OptikTest


class NotFound(LookupError):
    """İstenen test/batch/kayıt yok."""


def now_iso() -> str:
    return timezone.now().isoformat()


# ── Test ────────────────────────────────────────────────────────────────

_TEST_COLUMNS = ('course_code', 'course_name', 'exam_type', 'academic_year', 'semester')


def _test_to_dict(t: OptikTest) -> Dict[str, Any]:
    d = dict(t.data or {})
    d['test_id'] = t.test_id
    d['created_by'] = t.owner_id
    d.setdefault('created_at', t.created_at.isoformat() if t.created_at else '')
    return d


def load_test(test_id: str) -> Dict[str, Any]:
    try:
        return _test_to_dict(OptikTest.objects.get(test_id=test_id))
    except OptikTest.DoesNotExist:
        raise NotFound(f"Test bulunamadı: {test_id}")


def save_test(test_id: str, data: Dict[str, Any]) -> None:
    """Test dict'ini kaydet. Yoksa oluşturur (data['created_by'] = user id)."""
    data = dict(data)
    data['test_id'] = test_id
    fields = {c: str(data.get(c) or '') for c in _TEST_COLUMNS}
    fields['is_approved'] = bool(data.get('is_approved'))
    fields['deleted'] = bool(data.get('deleted'))
    obj = OptikTest.objects.filter(test_id=test_id).first()
    if obj is None:
        OptikTest.objects.create(test_id=test_id, owner_id=data['created_by'], data=data, **fields)
        return
    for k, v in fields.items():
        setattr(obj, k, v)
    obj.data = data
    obj.save()


def get_test_obj(test_id: str) -> OptikTest:
    try:
        return OptikTest.objects.select_related('owner').get(test_id=test_id)
    except OptikTest.DoesNotExist:
        raise NotFound(f"Test bulunamadı: {test_id}")


# ── Batch ───────────────────────────────────────────────────────────────

def _batch_to_dict(b: OptikBatch) -> Dict[str, Any]:
    d = dict(b.data or {})
    d['batch_id'] = b.batch_id
    d['test_id'] = b.test.test_id
    d['status'] = b.status
    d.setdefault('created_at', b.created_at.isoformat() if b.created_at else '')
    return d


def load_batch(batch_id: str) -> Dict[str, Any]:
    try:
        return _batch_to_dict(OptikBatch.objects.select_related('test').get(batch_id=batch_id))
    except OptikBatch.DoesNotExist:
        raise NotFound(f"Batch bulunamadı: {batch_id}")


def save_batch(batch_id: str, data: Dict[str, Any]) -> None:
    data = dict(data)
    data['batch_id'] = batch_id
    obj = OptikBatch.objects.filter(batch_id=batch_id).first()
    status = data.get('status') or 'CREATED'
    if obj is None:
        test = get_test_obj(data['test_id'])
        OptikBatch.objects.create(batch_id=batch_id, test=test, status=status, data=data)
        return
    obj.status = status
    obj.data = data
    obj.save(update_fields=['status', 'data', 'updated_at'])


def update_batch_fields(batch_id: str, **updates: Any) -> Dict[str, Any]:
    """Batch dict'ine atomik (satır kilidiyle) alan yaz. Arka plan iş parçacığı için."""
    with transaction.atomic():
        obj = OptikBatch.objects.select_for_update().select_related('test').get(batch_id=batch_id)
        data = _batch_to_dict(obj)
        data.update(updates)
        obj.status = data.get('status') or obj.status
        obj.data = data
        obj.save(update_fields=['status', 'data', 'updated_at'])
    return data


def get_batch_obj(batch_id: str) -> OptikBatch:
    try:
        return OptikBatch.objects.select_related('test', 'test__owner').get(batch_id=batch_id)
    except OptikBatch.DoesNotExist:
        raise NotFound(f"Batch bulunamadı: {batch_id}")


def list_test_batch_ids(test_id: str) -> List[str]:
    return list(OptikBatch.objects.filter(test__test_id=test_id)
                .order_by('-created_at').values_list('batch_id', flat=True))


# ── Scores (kaynakta <batch_dir>/scores.json) ───────────────────────────

def load_scores(batch_id: str) -> Optional[Dict[str, Any]]:
    """Puanlama sonucu; puanlanmamışsa None."""
    scores = OptikBatch.objects.filter(batch_id=batch_id).values_list('scores', flat=True).first()
    return scores or None


def save_scores(batch_id: str, scores: Dict[str, Any]) -> None:
    updated = OptikBatch.objects.filter(batch_id=batch_id).update(scores=scores, updated_at=timezone.now())
    if not updated:
        raise NotFound(f"Batch bulunamadı: {batch_id}")


# ── Records (kaynakta <batch_dir>/records/<rid>.json) ────────────────────

def _record_to_dict(r: OptikRecord) -> Dict[str, Any]:
    d = dict(r.data or {})
    d['record_id'] = r.record_id
    return d


def list_records(batch_id: str) -> List[Dict[str, Any]]:
    return [_record_to_dict(r) for r in OptikRecord.objects.filter(batch__batch_id=batch_id)]


def get_record(batch_id: str, record_id: str) -> Dict[str, Any]:
    try:
        return _record_to_dict(OptikRecord.objects.get(batch__batch_id=batch_id, record_id=record_id))
    except OptikRecord.DoesNotExist:
        raise NotFound(f"Kayıt bulunamadı: {record_id}")


def save_record(batch_id: str, record_id: str, data: Dict[str, Any]) -> None:
    data = dict(data)
    data['record_id'] = record_id
    batch = OptikBatch.objects.only('id').get(batch_id=batch_id)
    OptikRecord.objects.update_or_create(
        batch=batch, record_id=record_id,
        defaults={
            'data': data,
            'student_no': str(data.get('student_no') or '')[:32],
            'booklet': str(data.get('booklet') or '')[:8],
        })


def delete_record(batch_id: str, record_id: str) -> bool:
    deleted, _ = OptikRecord.objects.filter(batch__batch_id=batch_id, record_id=record_id).delete()
    return deleted > 0


def count_records(batch_id: str) -> int:
    return OptikRecord.objects.filter(batch__batch_id=batch_id).count()


# ── Snapshots (kaynakta <batch_dir>/snapshots/vN/) ──────────────────────

def list_snapshot_rows(batch_id: str) -> List[OptikSnapshot]:
    return list(OptikSnapshot.objects.filter(batch__batch_id=batch_id).order_by('created_at'))


def get_snapshot_row(batch_id: str, version: str) -> OptikSnapshot:
    try:
        return OptikSnapshot.objects.get(batch__batch_id=batch_id, version=version)
    except OptikSnapshot.DoesNotExist:
        raise NotFound(f"Snapshot bulunamadı: {version}")


def create_snapshot_row(batch_id: str, version: str, metadata: Dict[str, Any],
                        records: List[Dict[str, Any]]) -> OptikSnapshot:
    batch = OptikBatch.objects.only('id').get(batch_id=batch_id)
    return OptikSnapshot.objects.create(batch=batch, version=version, metadata=metadata, records=records)


# ── Dosya yolları ───────────────────────────────────────────────────────

def media_root() -> str:
    return os.path.join(str(settings.MEDIA_ROOT), 'optik')


def get_batch_dir(batch_id: str) -> str:
    return os.path.join(media_root(), batch_id)


def get_upload_dir(batch_id: str) -> str:
    path = os.path.join(get_batch_dir(batch_id), 'uploads')
    os.makedirs(path, exist_ok=True)
    return path


def is_inside_batch_dir(batch_id: str, path: str) -> bool:
    """Kayıttaki dosya yolu gerçekten bu batch'in klasöründe mi (yol aşımı koruması)."""
    if not path:
        return False
    base = os.path.realpath(get_batch_dir(batch_id))
    target = os.path.realpath(path)
    return os.path.commonpath([base, target]) == base
