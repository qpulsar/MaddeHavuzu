"""
OMR okuma servisi: tek form okuma ve tekrarlanan öğrenci numarası tespiti.

Kaynak: omr_analysis/service_omr.py

Farklar:
- Bubble map yolu `settings.OPTIK_BUBBLE_MAP_PATH`'ten alınır.
- `process_form_image` isteğe bağlı `overlay_dir` alır; overlay varsayılan
  olarak görüntünün klasörüne (batch uploads) yazılır.
- Görüntü okuma/yazma `np.fromfile`/`imdecode` ile yapılır (Windows'ta
  ASCII olmayan yollarda cv2.imread başarısız oluyordu).
- Hiçbir ekranın kullanmadığı toplu okuma/doğrulama/istatistik fonksiyonları
  alınmadı (okuma arka planda `optik.services.background` ile yapılır).
"""
import os
import uuid
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np
from django.conf import settings

from optik import omr_core, store
from optik.store import now_iso


def get_bubble_map_path() -> str:
    return str(getattr(settings, "OPTIK_BUBBLE_MAP_PATH", "")
               or os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "bubble_map_v1.json"))


def load_bubble_map() -> Dict[str, Any]:
    return omr_core.load_map(get_bubble_map_path())


def _imread(path: str) -> Optional[np.ndarray]:
    """Unicode yol güvenli cv2.imread karşılığı."""
    try:
        data = np.fromfile(path, dtype=np.uint8)
    except OSError:
        return None
    if data.size == 0:
        return None
    return cv2.imdecode(data, cv2.IMREAD_COLOR)


def _imwrite(path: str, img: np.ndarray) -> bool:
    """Unicode yol güvenli cv2.imwrite karşılığı."""
    ext = os.path.splitext(path)[1] or ".png"
    ok, buf = cv2.imencode(ext, img)
    if not ok:
        return False
    buf.tofile(path)
    return True


def process_form_image(
    image_path: str,
    test_id: str,
    expected_booklets: List[str],
    num_items: int,
    overlay_dir: Optional[str] = None,
) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
    """
    Tek bir optik formu işle ve OMR oku.

    Returns:
        (success, record_dict, error_message)
    """
    try:
        bubble_map = load_bubble_map()

        img = _imread(image_path)
        if img is None:
            return False, None, f"Görüntü okunamadı: {image_path}"

        # Form hizalama (aşamalı + reprojection validation)
        warped, H, align_info = omr_core.warp_to_reference(img, bubble_map["alignment"])
        th_inv = omr_core.prep_binary(warped)

        roi_r = int(bubble_map["bubble"]["roi_radius_px"])

        # --- Pass 1: hizalama kalitesi için hızlı okuma ---
        pre_scores = omr_core.collect_all_bubble_scores(th_inv, bubble_map, roi_r)
        pre_adaptive = omr_core.compute_adaptive_thresholds(pre_scores)
        pre_sno, _ = omr_core.read_grid(
            th_inv, bubble_map["student_no"], roi_r,
            pre_adaptive["min_fill_student_no"],
            pre_adaptive["delta_student_no"],
            force_multi_if_two_strong=True
        )

        # --- Hizalama düzeltmesi: yalnızca öğrenci no hatalıysa ---
        align_ox, align_oy = 0.0, 0.0
        if "?" in pre_sno or "!" in pre_sno:
            align_ox, align_oy = omr_core.compute_alignment_correction(th_inv, bubble_map)
            if align_ox != 0 or align_oy != 0:
                bubble_map = omr_core.apply_offset_to_map(bubble_map, align_ox, align_oy)

        # --- Pass 2: tam okuma (offset yoksa Pass 1 skorları geçerli) ---
        if align_ox != 0 or align_oy != 0:
            all_scores = omr_core.collect_all_bubble_scores(th_inv, bubble_map, roi_r)
            adaptive = omr_core.compute_adaptive_thresholds(all_scores)
        else:
            adaptive = pre_adaptive

        student_no, st_dbg = omr_core.read_grid(
            th_inv, bubble_map["student_no"], roi_r,
            adaptive["min_fill_student_no"],
            adaptive["delta_student_no"],
            force_multi_if_two_strong=True
        )

        class_code, cc_dbg = omr_core.read_grid(
            th_inv, bubble_map["class_code"], roi_r,
            adaptive["min_fill_class_code"],
            adaptive["delta"],
            force_multi_if_two_strong=True
        )

        booklet, b_dbg = omr_core.read_row(
            th_inv, bubble_map["booklet"], roi_r,
            adaptive["min_fill_booklet"],
            adaptive["delta"]
        )

        answers, a_dbg = omr_core.read_answers(
            th_inv, bubble_map["answers"], roi_r,
            adaptive["min_fill_answers"],
            adaptive["delta"],
            num_items=num_items or 0
        )

        # Oturma düzeni (opsiyonel)
        seating_result = None
        seating_dbg = None
        if "seating" in bubble_map and bubble_map["seating"].get("type") == "grid_explicit":
            seating_result, seating_dbg = omr_core.read_seating(
                th_inv, bubble_map["seating"], roi_r,
                adaptive["min_fill_seating"],
                adaptive["delta"]
            )

        # Overlay görüntüsü kaydet (her zaman)
        overlay = omr_core.draw_overlay(warped, bubble_map, th_inv, adaptive=adaptive, num_items=num_items or 0)
        overlay_filename = f"overlay_{uuid.uuid4().hex[:8]}.png"
        overlay_path = os.path.join(overlay_dir or os.path.dirname(image_path), overlay_filename)
        _imwrite(overlay_path, overlay)

        # Doğrulama uyarıları
        warnings = []
        if "?" in student_no or "!" in student_no:
            warnings.append(f"Öğrenci numarası sorunlu: {student_no}")
        # Tek kitapçık: OMR ne okursa okusun sabitle; çoklu: eşleşmezse uyar
        if len(expected_booklets) == 1:
            booklet = expected_booklets[0]
        elif booklet not in expected_booklets:
            warnings.append(f"Kitapçık eşleşmedi: {booklet} (beklenen: {expected_booklets})")

        record = {
            "record_id": f"rec_{uuid.uuid4().hex[:8]}",
            "student_no": student_no,
            "class_code": class_code,
            "booklet": booklet,
            "answers": answers,
            "seating": seating_result,
            "image_path": image_path,
            "overlay_path": overlay_path,
            "processed_at": now_iso(),
            "omr_confidence": align_info["confidence"],
            "warnings": warnings if warnings else None,
            "debug": {
                "student_no": st_dbg,
                "class_code": cc_dbg,
                "booklet": b_dbg,
                "answers": a_dbg,
                "seating": seating_dbg,
                "adaptive_thresholds": adaptive,
                "alignment_correction": {"ox": align_ox, "oy": align_oy},
                "alignment": align_info,
            }
        }

        return True, record, None

    except Exception as e:
        return False, None, f"OMR okuma hatası: {str(e)}"


def detect_duplicate_students(batch_id: str) -> List[Dict[str, Any]]:
    """Batch içinde aynı öğrenci numarasına sahip kayıtları bul."""
    student_counts: Dict[str, List[Dict[str, Any]]] = {}

    for record in store.list_records(batch_id):
        student_no = record.get("student_no")
        if student_no:
            student_counts.setdefault(student_no, []).append(record)

    return [
        {"student_no": sno, "count": len(recs), "records": recs}
        for sno, recs in student_counts.items() if len(recs) > 1
    ]


