"""
Optik Batch -> ExamData Adaptörü
================================
Kaynak: cheating/service_adapter.py. `omr_analysis` servisleri yerine
`optik.store` üzerinden okur (batch dict → test dict → scores).

Kodlama (kaynakla aynı)
-----------------------
- "A" -> 1, "B" -> 2, ..., "E" -> 5
- "" (boş) veya "?" -> 0
- "!" (çoklu işaret) -> -1
- Sayısal seçenek (1..9) doğrudan kabul edilir.

Anahtar için aynı kodlama. Geçerli harf anahtarı olmayan maddeler ("*" hatalı
madde, boş anahtar vb.) kopya kanıtı taşıyamaz; analizden çıkarılır ve meta
uyarısına yazılır. (Kaynakta bu durumda analiz tümüyle hata veriyordu.)

Kitapçık / Permütasyon
----------------------
- Tek kitapçıklı sınav: permütasyon birim (identity).
- Çok kitapçıklı: Madde Bilgileri sayfasındaki kitapçık eşleştirmesi
  (test.booklet_mapping, A referans) kullanılır: {"B": {"Q1": 5}} → B'nin 1.
  sorusu A'nın 5. sorusudur. Eşleştirme girilmemiş madde aynı sıradadır.
  (Kaynak, hiçbir ekranın yazmadığı test.permutations alanını arıyordu.)
"""

from __future__ import annotations

from typing import Any, Dict, Tuple

import numpy as np

from kopya.engine.core import ExamData
from optik import store


_LETTER_TO_INT = {
    "A": 1, "B": 2, "C": 3, "D": 4, "E": 5,
    "": 0, " ": 0, "?": 0,   # boş
    "!": -1,                  # çoklu
}


class AdapterError(Exception):
    """Adaptör dönüşümü sırasında çözülemeyen durum."""


def _encode_letter(x: Any) -> int:
    if x is None:
        return 0
    s = str(x).strip().upper()
    if s in _LETTER_TO_INT:
        return _LETTER_TO_INT[s]
    # Sayısal seçenek (1..9) doğrudan kabul et
    if s.isdigit():
        v = int(s)
        if 1 <= v <= 9:
            return v
    raise AdapterError(f"tanımsız cevap kodu: {x!r}")


def _sorted_qids(item_ids) -> list:
    """Q1, Q2, ..., Q10 gibi kimlikleri sayısal sırala."""
    def _key(x):
        s = str(x).strip()
        if s.startswith("Q") and s[1:].isdigit():
            return (0, int(s[1:]))
        return (1, s)
    return sorted(item_ids, key=_key)


def _booklet_permutations(test: Dict[str, Any], booklets: list, n_items: int) -> np.ndarray:
    """[kitapçık, pozisyon] → kanonik (A kitapçığı) madde indeksi."""
    if len(booklets) == 1:
        return np.arange(n_items, dtype=np.int32).reshape(1, -1)
    if "A" not in booklets:
        raise AdapterError("Çok kitapçıklı sınavda referans A kitapçığının cevap anahtarı yok.")
    mapping = test.get("booklet_mapping") or {}
    perms = np.zeros((len(booklets), n_items), dtype=np.int32)
    for b_idx, b in enumerate(booklets):
        b_map = mapping.get(b, {}) if b != "A" else {}
        row = []
        for pos in range(n_items):
            try:
                target = int(b_map.get(f"Q{pos + 1}", pos + 1))
            except (TypeError, ValueError):
                target = 0
            if not 1 <= target <= n_items:
                raise AdapterError(f"Kitapçık {b} Q{pos + 1}: eşleştirme değeri geçersiz.")
            row.append(target - 1)
        if len(set(row)) != n_items:
            raise AdapterError(
                f"Kitapçık {b} eşleştirmesinde aynı A maddesi birden fazla soruya verilmiş. "
                f"Madde Bilgileri sayfasındaki kitapçık eşleştirmesini düzeltin.")
        perms[b_idx] = row
    return perms


def batch_to_exam_data(batch_id: str) -> Tuple[ExamData, Dict[str, Any]]:
    """Optik batch verisinden ExamData + okunabilir meta üret.

    Meta: {"batch_id", "test_id", "course_code", "course_name", "exam_type",
           "n_records", "n_items", "n_options", "booklets", "warnings":[]}
    """
    warnings: list[str] = []

    try:
        batch = store.load_batch(batch_id)
    except store.NotFound:
        raise AdapterError(f"Batch bulunamadı: {batch_id}")
    test_id = batch.get("test_id")
    if not test_id:
        raise AdapterError("Batch'in test kimliği (test_id) boş.")
    try:
        test = store.load_test(test_id)
    except store.NotFound:
        raise AdapterError(f"Test bulunamadı: {test_id}")

    scores = store.load_scores(batch_id)
    if not scores:
        raise AdapterError(
            "Bu batch için henüz puanlama yapılmamış. Kopya analizi için "
            "önce Optik Okuma modülünde formları puanlayın.")

    records = scores.get("records", [])
    if not records:
        raise AdapterError("Puanlanmış kayıt listesi boş.")

    # Cevap anahtarları
    answer_keys = test.get("answer_keys", {}) or {}
    if not answer_keys:
        raise AdapterError("Testin cevap anahtarı (answer_keys) boş.")

    booklets = list(sorted(answer_keys.keys()))
    n_booklets = len(booklets)
    booklet_to_idx = {b: i for i, b in enumerate(booklets)}

    # Madde kimlikleri — ilk kitapçığın anahtarından (hepsi aynı sayıda olmalı)
    first_ak = answer_keys[booklets[0]]
    item_ids = _sorted_qids(first_ak.keys())
    n_items = len(item_ids)
    if n_items == 0:
        raise AdapterError("Cevap anahtarında madde yok.")

    # Tekdüze madde sayısı kontrolü
    for b in booklets:
        if len(answer_keys[b]) != n_items:
            raise AdapterError(
                f"Kitapçık {b} için madde sayısı ({len(answer_keys[b])}) "
                f"diğerlerinden farklı ({n_items})."
            )

    perm_array = _booklet_permutations(test, booklets, n_items)

    # Anahtarı kanonik uzayda birleştir. Kural: permutation[b, pozisyon] =
    # kanonik indeks. İki kitapçık aynı kanonik madde için aynı harfe sahip
    # OLMAK ZORUNDA (seçenek karıştırma yok — spec §2).
    canonical_key = np.zeros(n_items, dtype=np.int8)
    invalid_key = np.zeros(n_items, dtype=bool)
    for b_name, b_idx in booklet_to_idx.items():
        ak = answer_keys[b_name]
        for pos, item_id in enumerate(item_ids):
            canonical_idx = int(perm_array[b_idx, pos])
            try:
                v = _encode_letter(ak.get(item_id, ""))
            except AdapterError:
                v = 0
            if v <= 0:
                invalid_key[canonical_idx] = True
            elif canonical_key[canonical_idx] == 0:
                canonical_key[canonical_idx] = v
            elif canonical_key[canonical_idx] != v:
                raise AdapterError(
                    f"Kitapçık {b_name} {item_id}: anahtar, eşleştiği A kitapçığı "
                    f"maddesiyle aynı değil. Kitapçık eşleştirmesini kontrol edin "
                    f"(seçenek karıştırma desteklenmez).")

    # Geçerli anahtarı olmayan maddeleri çıkar (kanonik = A kitapçığı sırası)
    keep = ~invalid_key
    if not keep.any():
        raise AdapterError("Geçerli cevap anahtarı olan madde yok.")
    if invalid_key.any():
        dropped = [item_ids[i] for i in np.flatnonzero(invalid_key)]
        warnings.append(
            f"Geçerli anahtarı olmayan {len(dropped)} madde (hatalı '*' veya boş) "
            f"analiz dışı bırakıldı: {', '.join(dropped)}")
    new_index = np.cumsum(keep) - 1           # eski kanonik → yeni kanonik
    kept_positions = keep[perm_array]          # [kitapçık, pozisyon] tutulacak mı
    canonical_key = canonical_key[keep]
    perm_array = np.stack([new_index[perm_array[b][kept_positions[b]]]
                           for b in range(n_booklets)]).astype(np.int32)

    # Kayıtları matrise dök
    n_students = len(records)
    n_kept = int(keep.sum())
    responses = np.zeros((n_students, n_kept), dtype=np.int8)
    booklet_arr = np.zeros(n_students, dtype=np.int32)
    student_ids = np.empty(n_students, dtype=object)
    seat_codes = np.empty(n_students, dtype=object)
    excluded = np.zeros(n_students, dtype=bool)

    for si, rec in enumerate(records):
        sno = rec.get("student_no") or f"rec_{si}"
        student_ids[si] = str(sno)
        b_name = rec.get("booklet") or booklets[0]
        if b_name not in booklet_to_idx:
            warnings.append(f"kayıt {sno}: bilinmeyen kitapçık {b_name}, dışlanıyor")
            excluded[si] = True
            continue
        booklet_arr[si] = booklet_to_idx[b_name]
        seating = rec.get("seating") or {}
        seat_codes[si] = str(seating.get("cell_id", "") or "")

        item_scores = rec.get("item_scores", {}) or {}
        if not item_scores:
            warnings.append(f"kayıt {sno}: item_scores boş, dışlanıyor")
            excluded[si] = True
            continue
        b_positions = [item_ids[p] for p in np.flatnonzero(kept_positions[booklet_arr[si]])]
        for pos, item_id in enumerate(b_positions):
            entry = item_scores.get(item_id, {})
            raw = entry.get("student_answer", "") if isinstance(entry, dict) else ""
            try:
                v = _encode_letter(raw)
            except AdapterError:
                v = -1  # çözülemez -> çoklu/geçersiz kabul
            responses[si, pos] = v

    n_options = int(test.get("num_options") or 5)

    exam = ExamData(
        responses=responses,
        key=canonical_key,
        booklet=booklet_arr,
        permutation=perm_array,
        student_id=student_ids,
        n_options=n_options,
        seat_code=seat_codes if any(seat_codes) else None,
        excluded=excluded if excluded.any() else None,
    )

    meta = {
        "batch_id": batch_id,
        "test_id": test_id,
        "course_code": test.get("course_code", ""),
        "course_name": test.get("course_name", ""),
        "exam_type": test.get("exam_type", ""),
        "n_records": n_students,
        "n_items": n_kept,
        "n_options": n_options,
        "booklets": booklets,
        "warnings": warnings,
    }
    return exam, meta


__all__ = ["batch_to_exam_data", "AdapterError"]
