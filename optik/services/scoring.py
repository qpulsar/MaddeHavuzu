"""
Puanlama servisi: OMR sonuçlarını cevap anahtarıyla karşılaştırıp puanlar.

Kaynak: omr_analysis/service_scoring.py

Farklar:
- scores.json yerine `store.load_scores/save_scores` kullanılır.
- `score_batch(batch_id, user)`: user Django User (veya id); `scored_by` = id.
- Düzeltme: `score_batch` metadata'sı döngüden kalan değişkenlerle
  kuruluyordu (tüm kayıtlar atlanınca NameError). Artık açıkça hesaplanır:
  {"booklet": ilk kullanılan kitapçık | None, "booklets": [...],
   "total_records": n, "max_points": {item: puan} (ilk kitapçık),
   "max_points_by_booklet": {kitapçık: {item: puan}}}.
- Düzeltme: `update_scores_json` kayıtları student_no ile eşliyordu (aynı
  numaralı iki kayıt çakışıyordu); artık record_id ile eşlenir.
"""
import logging
from typing import Any, Dict, List, Optional

from optik import store
from optik.services import core as service
from optik.services import override as override_service
from optik.store import now_iso

logger = logging.getLogger(__name__)


def score_single_record(
    record: Dict[str, Any],
    answer_key: Dict[str, str],
    item_points: Dict[str, float]
) -> Dict[str, Any]:
    """
    Tek bir kayıt için puanlama yap.

    Args:
        record: OMR kayıt verisi
        answer_key: Cevap anahtarı {Q1: A, Q2: B, ...}
        item_points: Madde puanları {Q1: 2.5, Q2: 2.5, ...}
    """
    student_answers = record.get("answers", {})

    # Liste formatındaysa dict'e çevir
    if isinstance(student_answers, list):
        student_answers = {f"Q{i}": ans for i, ans in enumerate(student_answers, 1)}

    item_scores = {}
    correct_count = 0
    wrong_count = 0
    blank_count = 0

    for item_id, correct_answer in answer_key.items():
        student_answer = student_answers.get(item_id, "")
        point = item_points.get(item_id, 0.0)

        is_student_blank = not student_answer or student_answer == "?"
        is_key_blank = not correct_answer or correct_answer == "?"

        # Hatalı soru - herkese tam puan
        if correct_answer == "*":
            item_scores[item_id] = {
                "student_answer": student_answer if not is_student_blank else "",
                "correct_answer": "*",
                "points": point,
                "max_points": point,
                "status": "correct"
            }
            correct_count += 1
            continue

        if is_student_blank:
            item_scores[item_id] = {
                "student_answer": "",
                "correct_answer": correct_answer,
                "points": 0.0,
                "max_points": point,
                "status": "blank"
            }
            blank_count += 1
        elif student_answer == "!":
            # Çoklu/belirsiz işaret - yanlış say
            item_scores[item_id] = {
                "student_answer": "!",
                "correct_answer": correct_answer,
                "points": 0.0,
                "max_points": point,
                "status": "multi"
            }
            wrong_count += 1
        elif is_key_blank:
            # Anahtar boş ama öğrenci cevaplamış: puansız, sayılara dahil değil
            item_scores[item_id] = {
                "student_answer": student_answer,
                "correct_answer": "",
                "points": 0.0,
                "max_points": 0.0,
                "status": "not_graded"
            }
        elif student_answer == correct_answer:
            item_scores[item_id] = {
                "student_answer": student_answer,
                "correct_answer": correct_answer,
                "points": point,
                "max_points": point,
                "status": "correct"
            }
            correct_count += 1
        else:
            item_scores[item_id] = {
                "student_answer": student_answer,
                "correct_answer": correct_answer,
                "points": 0.0,
                "max_points": point,
                "status": "wrong"
            }
            wrong_count += 1

    total_points = sum(item["points"] for item in item_scores.values())
    max_points = sum(item["max_points"] for item in item_scores.values())

    return {
        "record_id": record.get("record_id"),
        "student_no": record.get("student_no"),
        "booklet": record.get("booklet"),
        "seating": record.get("seating", {}),
        "item_scores": item_scores,
        "summary": {
            "correct": correct_count,
            "wrong": wrong_count,
            "blank": blank_count,
            "total_questions": len(answer_key),
            "total_points": round(total_points, 2),
            "max_points": round(max_points, 2),
            "percentage": round((total_points / max_points * 100) if max_points > 0 else 0, 2)
        },
        "scored_at": now_iso()
    }


def _class_statistics(scored_records: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not scored_records:
        return {}
    all_scores = [r["summary"]["total_points"] for r in scored_records]
    all_percentages = [r["summary"]["percentage"] for r in scored_records]
    return {
        "mean": round(sum(all_scores) / len(all_scores), 2),
        "max": round(max(all_scores), 2),
        "min": round(min(all_scores), 2),
        "mean_percentage": round(sum(all_percentages) / len(all_percentages), 2),
        "pass_count": sum(1 for p in all_percentages if p >= 50),
        "fail_count": sum(1 for p in all_percentages if p < 50)
    }


def score_batch(batch_id: str, user: Any) -> Dict[str, Any]:
    """
    Batch'in tüm kayıtlarını puanla ve sonucu kaydet.

    Args:
        user: Puanlayan kullanıcı (User nesnesi veya id)

    Returns:
        Puanlama verisi (scores dict)
    """
    batch = service.get_batch(batch_id)
    test = service.get_test(batch["test_id"])

    records = service.get_batch_records(batch_id)
    if not records:
        raise ValueError("Batch'de kayıt yok")

    answer_keys = test.get("answer_keys", {})
    test_booklets = test.get("booklets", [])
    items = test.get("items", {})

    scored_records = []
    points_by_booklet: Dict[str, Dict[str, float]] = {}

    for record in records:
        try:
            # Override'ları uygula (student_no, booklet vb.)
            overrides = record.get("overrides", {})
            if overrides:
                record = override_service.apply_overrides(record, overrides)

            # Kaydın kitapçığını belirle
            booklet = record.get("booklet")
            if not booklet:
                if len(test_booklets) == 1:
                    booklet = test_booklets[0]
                elif len(answer_keys) == 1:
                    booklet = list(answer_keys.keys())[0]
                else:
                    logger.info("Kayıt %s: kitapçık belirlenemedi, atlanıyor", record.get("record_id"))
                    continue

            if booklet not in answer_keys:
                logger.info("Kayıt %s: kitapçık %s için cevap anahtarı yok, atlanıyor",
                            record.get("record_id"), booklet)
                continue

            answer_key = answer_keys[booklet]

            # Her madde için puan belirle
            item_points = {}
            for item_id in answer_key.keys():
                if item_id in items:
                    item_points[item_id] = items[item_id].get("points", 0.0)
                else:
                    item_points[item_id] = 100.0 / len(answer_key) if answer_key else 0.0

            scored_records.append(score_single_record(record, answer_key, item_points))
            points_by_booklet.setdefault(booklet, item_points)
        except Exception as e:
            logger.warning("Kayıt puanlanamadı: %s - %s", record.get("record_id"), e)

    used_booklets = list(points_by_booklet.keys())
    first_booklet = used_booklets[0] if used_booklets else None

    scores_data = {
        "batch_id": batch_id,
        "test_id": test["test_id"],
        "scored_at": now_iso(),
        "scored_by": service.user_id(user),
        "records": scored_records,
        "class_statistics": _class_statistics(scored_records),
        "metadata": {
            "booklet": first_booklet,
            "booklets": used_booklets,
            "total_records": len(scored_records),
            "max_points": points_by_booklet.get(first_booklet, {}) if first_booklet else {},
            "max_points_by_booklet": points_by_booklet,
        }
    }

    store.save_scores(batch_id, scores_data)
    service.update_batch_status(batch_id, "SCORED")

    return scores_data


def get_batch_scores(batch_id: str) -> Optional[Dict[str, Any]]:
    """Batch puanlama sonuçlarını getir (puanlanmamışsa None)."""
    return store.load_scores(batch_id)


def get_student_score(batch_id: str, student_no: str) -> Optional[Dict[str, Any]]:
    """Belirli bir öğrencinin (ilk eşleşen) puanını getir."""
    scores = get_batch_scores(batch_id)
    if not scores:
        return None
    for record in scores.get("records", []):
        if record.get("student_no") == student_no:
            return record
    return None


def update_scores_json(batch_id: str) -> None:
    """
    Açık uçlu puanlar eklendikten sonra puanlama sonucunu güncelle.

    Kayıtlardaki open_scores / open_total değerlerini puanlama sonucuna
    yansıtır, toplamları ve sınıf istatistiklerini yeniden hesaplar.
    """
    scores = get_batch_scores(batch_id)
    if not scores:
        return

    batch = service.get_batch(batch_id)
    test = service.get_test(batch["test_id"])
    items = test.get("items", {})
    question_counts = test.get("question_counts", {})

    # record_id ile indeksle (aynı öğrenci no'lu kayıtlar çakışmasın)
    records_by_id = {r.get("record_id"): r for r in service.get_batch_records(batch_id)}

    for scored_rec in scores.get("records", []):
        rec = records_by_id.get(scored_rec.get("record_id"))
        if rec is None:
            continue

        open_scores = rec.get("open_scores", {}) or {}
        open_total = rec.get("open_total", 0) or 0

        scored_rec["open_scores"] = open_scores
        scored_rec["open_total"] = open_total

        # Toplam = MCQ + açık uçlu
        mcq_total = sum(item["points"] for item in scored_rec.get("item_scores", {}).values())
        total_points = mcq_total + open_total

        mcq_max = sum(item["max_points"] for item in scored_rec.get("item_scores", {}).values())
        open_max = sum(items.get(item_id, {}).get("points", 0) for item_id in open_scores.keys())

        # open_scores boş ama testte açık uçlu soru varsa max'a ekle
        if question_counts.get("OPEN", 0) > 0 and not open_scores:
            for item_data in items.values():
                if item_data.get("type") == "OPEN":
                    open_max += item_data.get("points", 0)

        total_max = mcq_max + open_max

        scored_rec["summary"]["total_points"] = round(total_points, 2)
        scored_rec["summary"]["max_points"] = round(total_max, 2)
        scored_rec["summary"]["percentage"] = round(
            (total_points / total_max * 100) if total_max > 0 else 0, 2
        )

    scored_records = scores.get("records", [])
    if scored_records:
        scores["class_statistics"] = _class_statistics(scored_records)

    scores["updated_at"] = now_iso()
    store.save_scores(batch_id, scores)
