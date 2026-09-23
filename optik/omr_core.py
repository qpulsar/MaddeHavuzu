import copy
import json
import cv2
import numpy as np
from typing import Dict, Any, List, Tuple, Optional

# Target (reference) canvas size after alignment/warp
TARGET_W, TARGET_H = 2480, 3508

# =========================
# Decision parameters
# =========================
DELTA = 0.06  # top - second below this => multi/ambiguous

# Field-specific minimum fill thresholds (tune with your data)
MIN_FILL_STUDENT_NO = 0.44
MIN_FILL_CLASS_CODE = 0.46
MIN_FILL_BOOKLET = 0.43
MIN_FILL_ANSWERS = 0.52
MIN_FILL_SEATING = 0.46
DELTA_STUDENT_NO = 0.05


def load_map(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# =============================================================
# Rotation-first alignment (T10337-inspired, for scanner input)
# =============================================================

def detect_rotation_angle(gray: np.ndarray) -> float:
    """
    Detect the dominant rotation angle of a scanned form using Hough lines.

    Uses the form's structural lines (borders, grids, printed rectangles)
    which are far more numerous and reliable than 4 small corner markers.

    Returns angle in degrees (positive = counterclockwise).
    Returns 0.0 if no reliable angle is found.
    """
    h, w = gray.shape[:2]
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blur, 50, 150)

    # Detect long structural lines only
    min_len = max(200, int(w * 0.08))
    lines = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=100,
                            minLineLength=min_len, maxLineGap=10)
    if lines is None:
        return 0.0

    angles: List[float] = []
    for line in lines:
        x1, y1, x2, y2 = line[0]
        deg = float(np.degrees(np.arctan2(y2 - y1, x2 - x1)))
        # Near-horizontal lines (deviation from 0)
        if abs(deg) < 10:
            angles.append(deg)
        # Near-vertical lines (deviation from +-90) → convert to horizontal equiv
        elif abs(abs(deg) - 90) < 10:
            angles.append(deg - 90 if deg > 0 else deg + 90)

    if len(angles) < 10:
        return 0.0

    med = float(np.median(angles))
    # If spread is too large, detection is unreliable
    iqr = float(np.percentile(angles, 75) - np.percentile(angles, 25))
    if iqr > 1.0:
        return 0.0

    # Clamp to reasonable scanner skew range
    return max(-5.0, min(5.0, med))


# Asama parametreleri: (roi_pct, geometric_tolerance, contour_circularity_min)
# Asama 1 = standart tarama, %5 tolerans
# Asama 2 = hafif kaymis tarama, daha gevsek
_ALIGNMENT_STAGES = [
    (0.14, 0.05, 0.50),   # 1: standart — Balikesir/Sakarya formlari icin
    (0.18, 0.12, 0.40),   # 2: hafif bozuk tarama
]

# Post-warp validation: dst marker pozisyonlarinda darkness threshold
# (siyah noktanin ortalama gri degeri < bu esikten kucuk olmali)
MAX_MARKER_MEAN_GRAY = 120  # 0=siyah, 255=beyaz


def _find_in_corner_rois(
    work_gray: np.ndarray,
    roi_pct: float,
    circ_min: float,
) -> Optional[np.ndarray]:
    """4 kose ROI'sinde tek aday ara. Bulunamazsa None."""
    h, w = work_gray.shape[:2]
    blur = cv2.GaussianBlur(work_gray, (9, 9), 2)
    th = cv2.adaptiveThreshold(
        blur, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV, 51, 7
    )
    th = cv2.morphologyEx(th, cv2.MORPH_OPEN,
                          np.ones((3, 3), np.uint8), iterations=1)

    scale = w / TARGET_W
    expected_r = int(55 * scale)
    expected_area = np.pi * (expected_r ** 2)

    roi_w, roi_h = int(w * roi_pct), int(h * roi_pct)
    rois = {
        "TL": (0, 0, roi_w, roi_h),
        "TR": (w - roi_w, 0, w, roi_h),
        "BL": (0, h - roi_h, roi_w, h),
        "BR": (w - roi_w, h - roi_h, w, h),
    }

    pts: Dict[str, Tuple[float, float]] = {}
    for name, (x0, y0, x1, y1) in rois.items():
        roi = th[y0:y1, x0:x1]
        contours, _ = cv2.findContours(roi, cv2.RETR_EXTERNAL,
                                       cv2.CHAIN_APPROX_SIMPLE)
        best = None
        best_score = -1.0
        for c in contours:
            area = cv2.contourArea(c)
            if area < expected_area * 0.20 or area > expected_area * 3.0:
                continue
            peri = cv2.arcLength(c, True)
            if peri <= 0:
                continue
            circularity = 4 * np.pi * area / (peri * peri)
            x, y, bw, bh = cv2.boundingRect(c)
            ar = bw / float(bh) if bh else 0.0
            if circularity > circ_min and 0.6 < ar < 1.4:
                mask_roi = work_gray[y0:y1, x0:x1][y:y + bh, x:x + bw]
                if mask_roi.size > 0 and float(np.mean(mask_roi)) < 130:
                    score = area * circularity
                    if score > best_score:
                        M = cv2.moments(c)
                        if M["m00"] == 0:
                            continue
                        cx = x0 + (M["m10"] / M["m00"])
                        cy = y0 + (M["m01"] / M["m00"])
                        best = (float(cx), float(cy))
                        best_score = score
        if best is None:
            return None
        pts[name] = best

    return np.array([pts["TL"], pts["TR"], pts["BL"], pts["BR"]],
                    dtype=np.float32)


def _validate_quad_geometry(pts: np.ndarray, tol: float) -> Tuple[bool, float]:
    """4 noktanin yaklasik dikdortgen olusturup olusturmadigini kontrol et.

    Donus: (gecti_mi, max_sapma_oran)
    """
    w_top = float(np.linalg.norm(pts[1] - pts[0]))
    w_bot = float(np.linalg.norm(pts[3] - pts[2]))
    h_left = float(np.linalg.norm(pts[2] - pts[0]))
    h_right = float(np.linalg.norm(pts[3] - pts[1]))
    w_diff = abs(w_top - w_bot) / max(w_top, w_bot, 1.0)
    h_diff = abs(h_left - h_right) / max(h_left, h_right, 1.0)
    max_sapma = max(w_diff, h_diff)
    return (max_sapma <= tol), max_sapma


def _find_alignment_points_staged(
    work_gray: np.ndarray,
) -> Optional[Tuple[np.ndarray, int, float]]:
    """Asamali arama. (sirali_noktalar, asama_no, max_geometric_sapma) doner.

    Hicbir asama gecmediyse None.
    """
    for stage_idx, (roi_pct, geom_tol, circ_min) in enumerate(_ALIGNMENT_STAGES, 1):
        pts = _find_in_corner_rois(work_gray, roi_pct, circ_min)
        if pts is None:
            continue
        ok, sapma = _validate_quad_geometry(pts, geom_tol)
        if ok:
            return pts, stage_idx, sapma
    return None


def _validate_post_warp(warped_bgr: np.ndarray, dst_pts: np.ndarray) -> Tuple[bool, float, str]:
    """Warped goruntude beklenen marker pozisyonlarinda gercekten koyu daire var mi?

    Yelpaze/dejenere warp'larda dst pozisyonlarinda piksel beyaz veya garbage olur.
    Donus: (gecti_mi, en_acik_marker_gri, mesaj)
    """
    gray = cv2.cvtColor(warped_bgr, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape[:2]
    sample_radius = 25  # marker yaricapinda kucuk pencere
    means = []
    for x, y in dst_pts:
        x, y = int(x), int(y)
        x0 = max(0, x - sample_radius)
        x1 = min(w, x + sample_radius)
        y0 = max(0, y - sample_radius)
        y1 = min(h, y + sample_radius)
        roi = gray[y0:y1, x0:x1]
        if roi.size == 0:
            return False, 255.0, "dst noktasi warped disinda"
        means.append(float(np.mean(roi)))
    max_mean = max(means)
    if max_mean > MAX_MARKER_MEAN_GRAY:
        return False, max_mean, (
            f"beklenen marker pozisyonlarinda yeterince koyu piksel yok "
            f"(en acik={max_mean:.0f}/255, esik {MAX_MARKER_MEAN_GRAY})"
        )
    return True, max_mean, "ok"


def warp_to_reference(
    img_bgr: np.ndarray,
    ref_alignment: Dict[str, Any],
) -> Tuple[np.ndarray, np.ndarray, Dict[str, Any]]:
    """
    Scan/photo'yu referans canvasa warp et.

    Asamali kose tespiti + geometric validation + reprojection error testi.
    Basarisizsa RuntimeError("alignment_failed: ...") firlatir — sahte sonuc
    uretilmez, kayit acikca reddedilir.

    Donus: (warped_image, H_matrix, alignment_info)
      alignment_info: {"stage": 1-3, "geometric_sapma": float,
                       "reprojection_error": float, "confidence": 0-1}
    """
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)

    dst_pts = np.array([
        [ref_alignment["points"][0]["x"], ref_alignment["points"][0]["y"]],
        [ref_alignment["points"][1]["x"], ref_alignment["points"][1]["y"]],
        [ref_alignment["points"][2]["x"], ref_alignment["points"][2]["y"]],
        [ref_alignment["points"][3]["x"], ref_alignment["points"][3]["y"]],
    ], dtype=np.float32)

    # --- 1. Deskew (yumusak rotasyon duzeltmesi) ---
    angle = detect_rotation_angle(gray)
    if abs(angle) > 0.1:
        h, w = gray.shape[:2]
        M_rot = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
        work_bgr = cv2.warpAffine(img_bgr, M_rot, (w, h),
                                  flags=cv2.INTER_LINEAR,
                                  borderMode=cv2.BORDER_REPLICATE)
        work_gray = cv2.cvtColor(work_bgr, cv2.COLOR_BGR2GRAY)
    else:
        work_bgr = img_bgr
        work_gray = gray

    # --- 2. Asamali kose tespiti ---
    result = _find_alignment_points_staged(work_gray)
    if result is None:
        raise RuntimeError(
            "alignment_failed: 4 kose markeri hicbir asamada bulunamadi "
            "(kotu tarama, eksik koseler veya sahte adaylar)."
        )
    src_pts, stage_idx, geom_sapma = result

    # --- 3. Homography ---
    H, _ = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, 5.0)
    if H is None:
        H = cv2.getPerspectiveTransform(src_pts, dst_pts)

    warped = cv2.warpPerspective(work_bgr, H, (TARGET_W, TARGET_H),
                                 flags=cv2.INTER_LINEAR)

    # --- 4. Post-warp validation: dst marker pozisyonlarinda koyu piksel var mi? ---
    pw_ok, max_marker_gray, pw_msg = _validate_post_warp(warped, dst_pts)
    if not pw_ok:
        raise RuntimeError(
            f"alignment_failed: post-warp dogrulama gecemedi "
            f"(asama {stage_idx}): {pw_msg}"
        )

    # Confidence: asama 1 = temiz, asama 2 = hafif gevsek
    stage_conf = {1: 0.95, 2: 0.80}.get(stage_idx, 0.65)
    # Marker darkness penalty: siyah marker (gri<60) = tam puan, esikte = 0.85
    darkness_factor = max(0.85, 1.0 - (max_marker_gray / MAX_MARKER_MEAN_GRAY) * 0.15)
    confidence = round(stage_conf * darkness_factor, 3)

    info = {
        "stage": stage_idx,
        "geometric_sapma": round(geom_sapma, 4),
        "max_marker_gray": round(max_marker_gray, 1),
        "confidence": confidence,
    }
    return warped, H, info


def compute_alignment_correction(
    th_inv: np.ndarray,
    bubble_map: Dict[str, Any],
    search_range: int = 20
) -> Tuple[float, float]:
    """
    After perspective warp, compute a fine-tuning (dx, dy) pixel offset.

    Uses a **max-per-group** metric: for each student_no column (12) and
    each answer row (20), only the highest-scoring bubble (the filled one)
    counts.  This avoids being fooled by background ink and only rewards
    offsets that centre filled bubbles.

    Returns (offset_x, offset_y) to ADD to all map coordinates.
    Returns (0, 0) if correction is unreliable or not beneficial.
    """
    roi_r = int(bubble_map["bubble"]["roi_radius_px"])
    h, w = th_inv.shape[:2]

    # Score map: average ink density in a square ROI around every pixel
    binary = (th_inv > 0).astype(np.float32)
    ks = 2 * roi_r + 1
    score_map = cv2.blur(binary, (ks, ks))

    # Student No grid centres — shape (cols, rows)
    sn = bubble_map["student_no"]
    sn_cols, sn_rows = sn["cols"], sn["rows"]
    sn_cx = np.zeros((sn_cols, sn_rows), dtype=np.int32)
    sn_cy = np.zeros((sn_cols, sn_rows), dtype=np.int32)
    for c in range(sn_cols):
        for r in range(sn_rows):
            sn_cx[c, r] = int(round(sn["anchor"]["x"] + c * sn["dx"]))
            sn_cy[c, r] = int(round(sn["anchor"]["y"] + r * sn["dy"]))

    # Answers grid centres — shape (num_q, choices)
    ans = bubble_map["answers"]
    num_q = min(20, ans["rows"])
    a_cols = ans["cols"]
    ans_cx = np.zeros((num_q, a_cols), dtype=np.int32)
    ans_cy = np.zeros((num_q, a_cols), dtype=np.int32)
    for q in range(num_q):
        for c in range(a_cols):
            ans_cx[q, c] = int(round(ans["anchor"]["x"] + c * ans["dx"]))
            ans_cy[q, c] = int(round(ans["anchor"]["y"] + q * ans["dy"]))

    best_score = -1.0
    best_ox, best_oy = 0, 0

    for oy in range(-search_range, search_range + 1):
        sn_py = np.clip(sn_cy + oy, 0, h - 1)
        ans_py = np.clip(ans_cy + oy, 0, h - 1)
        for ox in range(-search_range, search_range + 1):
            sn_px = np.clip(sn_cx + ox, 0, w - 1)
            sn_scores = score_map[sn_py, sn_px]          # (cols, rows)
            sn_total = float(np.sum(np.max(sn_scores, axis=1)))  # max per column

            ans_px = np.clip(ans_cx + ox, 0, w - 1)
            ans_scores = score_map[ans_py, ans_px]        # (num_q, choices)
            ans_total = float(np.sum(np.max(ans_scores, axis=1)))  # max per row

            total = sn_total + ans_total
            if total > best_score:
                best_score = total
                best_ox, best_oy = ox, oy

    # Sanity: boundary hit means the warp itself is bad — don't correct
    if abs(best_ox) >= search_range or abs(best_oy) >= search_range:
        return 0.0, 0.0

    # Quality gate: only apply if the best offset clearly beats (0, 0)
    sn_scores_base = score_map[
        np.clip(sn_cy, 0, h - 1), np.clip(sn_cx, 0, w - 1)
    ]
    ans_scores_base = score_map[
        np.clip(ans_cy, 0, h - 1), np.clip(ans_cx, 0, w - 1)
    ]
    base_score = (
        float(np.sum(np.max(sn_scores_base, axis=1)))
        + float(np.sum(np.max(ans_scores_base, axis=1)))
    )

    # Require at least 2 % improvement over uncorrected baseline
    if base_score > 0 and (best_score - base_score) / base_score < 0.02:
        return 0.0, 0.0

    return float(best_ox), float(best_oy)


def apply_offset_to_map(
    bubble_map: Dict[str, Any], ox: float, oy: float
) -> Dict[str, Any]:
    """Return a deep-copied bubble_map with all coordinates shifted by (ox, oy)."""
    m = copy.deepcopy(bubble_map)

    for key in ("student_no", "class_code", "answers"):
        if key in m and "anchor" in m[key]:
            m[key]["anchor"]["x"] += ox
            m[key]["anchor"]["y"] += oy

    if "booklet" in m and "anchor" in m["booklet"]:
        m["booklet"]["anchor"]["x"] += ox
        m["booklet"]["anchor"]["y"] += oy

    if "seating" in m and "cells" in m["seating"]:
        for cell in m["seating"]["cells"]:
            cell["x"] += ox
            cell["y"] += oy

    return m


def prep_binary(warped_bgr: np.ndarray) -> np.ndarray:
    """
    Create a binary inverted image where "ink" pixels are 255 and background is 0.
    """
    gray = cv2.cvtColor(warped_bgr, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (3, 3), 0)
    th = cv2.adaptiveThreshold(
        blur, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV, 31, 7
    )
    return th


def bubble_score(th_inv: np.ndarray, cx: float, cy: float, r: int) -> float:
    """
    Compute "ink density" in a square ROI around the bubble center.
    Returns fraction of pixels marked as ink (0..1).
    """
    h, w = th_inv.shape[:2]
    x0 = max(int(cx - r), 0)
    x1 = min(int(cx + r), w - 1)
    y0 = max(int(cy - r), 0)
    y1 = min(int(cy + r), h - 1)

    roi = th_inv[y0:y1 + 1, x0:x1 + 1]
    if roi.size == 0:
        return 0.0

    return float(np.mean(roi > 0))


def collect_all_bubble_scores(
    th_inv: np.ndarray,
    m: Dict[str, Any],
    roi_r: int
) -> Dict[str, Any]:
    """
    Collect bubble ink-density scores from ALL bubble positions on the form.
    Used to analyse per-form fill characteristics before reading fields.

    Returns dict with:
      - all_scores: flat list of every individual bubble score (~410 values)
      - row_maxes: max score per row/column (answers: per question, student_no: per digit)
                   Used for signal level estimation (bimodal: answered vs unanswered rows)
    """
    all_scores: List[float] = []
    row_maxes: List[float] = []

    # Answers grid (e.g. 50 rows x 5 cols) - max per question
    ans = m["answers"]
    ax, ay = ans["anchor"]["x"], ans["anchor"]["y"]
    adx, ady = ans["dx"], ans["dy"]
    for q in range(ans["rows"]):
        row_scores: List[float] = []
        for c in range(ans["cols"]):
            s = bubble_score(th_inv, ax + c * adx, ay + q * ady, roi_r)
            all_scores.append(s)
            row_scores.append(s)
        row_maxes.append(max(row_scores))

    # Student No grid (e.g. 12 cols x 10 rows) - max per digit column
    sn = m["student_no"]
    sx, sy = sn["anchor"]["x"], sn["anchor"]["y"]
    sdx, sdy = sn["dx"], sn["dy"]
    for col in range(sn["cols"]):
        col_scores: List[float] = []
        for row in range(sn["rows"]):
            s = bubble_score(th_inv, sx + col * sdx, sy + row * sdy, roi_r)
            all_scores.append(s)
            col_scores.append(s)
        row_maxes.append(max(col_scores))

    # Class Code grid (e.g. 4 cols x 10 rows) - max per digit column
    cc = m["class_code"]
    ccx, ccy = cc["anchor"]["x"], cc["anchor"]["y"]
    cdx, cdy = cc["dx"], cc["dy"]
    for col in range(cc["cols"]):
        col_scores_cc: List[float] = []
        for row in range(cc["rows"]):
            s = bubble_score(th_inv, ccx + col * cdx, ccy + row * cdy, roi_r)
            all_scores.append(s)
            col_scores_cc.append(s)
        row_maxes.append(max(col_scores_cc))

    return {"all_scores": all_scores, "row_maxes": row_maxes}


def compute_adaptive_thresholds(
    score_data: Dict[str, Any],
    floor: float = 0.30
) -> Dict[str, Any]:
    """
    Compute per-form adaptive thresholds from bubble score distribution.

    - bg = P25 of all individual bubble scores (background/unfilled level)
    - signal = P75 of per-row max scores (filled rows stand out clearly)
    - If gap < 0.12: no clear bimodal separation, use static defaults
    - Otherwise: adaptive = bg + 0.4 * gap, clamped between floor and static default
    """
    all_scores = score_data["all_scores"]
    row_maxes = score_data["row_maxes"]

    bg = float(np.percentile(all_scores, 25))
    signal = float(np.percentile(row_maxes, 75))
    gap = signal - bg

    result = {
        "adapted": False,
        "bg_level": round(bg, 4),
        "signal_level": round(signal, 4),
        "gap": round(gap, 4),
        "base_adaptive": None,
        "min_fill_answers": MIN_FILL_ANSWERS,
        "min_fill_student_no": MIN_FILL_STUDENT_NO,
        "min_fill_class_code": MIN_FILL_CLASS_CODE,
        "min_fill_booklet": MIN_FILL_BOOKLET,
        "min_fill_seating": MIN_FILL_SEATING,
        "delta": DELTA,
        "delta_student_no": DELTA_STUDENT_NO,
    }

    if gap < 0.12:
        return result

    base = max(floor, bg + 0.5 * gap)

    result["adapted"] = True
    result["base_adaptive"] = round(base, 4)
    result["min_fill_answers"] = round(min(MIN_FILL_ANSWERS, base), 4)
    result["min_fill_student_no"] = round(min(MIN_FILL_STUDENT_NO, base), 4)
    result["min_fill_class_code"] = round(min(MIN_FILL_CLASS_CODE, base), 4)
    # Booklet and seating: keep static (too few bubbles to benefit)

    # Adaptive delta: low-contrast forms (e.g. 200 DPI scans) need a lower
    # delta threshold.  Scale delta proportionally to the contrast gap,
    # using gap=0.40 as the "ideal" reference.  Clamp to [0.03, static].
    ref_gap = 0.40
    scale_factor = min(1.0, gap / ref_gap)
    result["delta"] = round(max(0.03, DELTA * scale_factor), 4)
    result["delta_student_no"] = round(max(0.03, DELTA_STUDENT_NO * scale_factor), 4)

    return result


def _decide_from_scores(scores: List[float], min_fill: float, delta: float) -> Tuple[str, int, float, float]:
    """
    Decide blank/multi/ok/borderline from a list of scores.

    Statuses:
      - "ok"         : top >= min_fill AND gap >= delta  (kesin tek cevap)
      - "borderline" : top < min_fill ama >= 0.85*min_fill VE gap >= delta
                       (kil payi esik altinda, en koyu acikca farkli — tek cevap kabul edilir)
      - "blank"      : top yetersiz veya gap delta altinda (esik altinda)
      - "multi"      : top >= min_fill AND gap < delta (iki yakin guclu isaret)

    Returns: (status, top_idx, top, top2)
    """
    if not scores:
        return "blank", 0, 0.0, 0.0

    top_idx = int(np.argmax(scores))
    top = float(scores[top_idx])

    sorted_scores = sorted(scores, reverse=True)
    top2 = float(sorted_scores[1]) if len(sorted_scores) > 1 else 0.0
    gap = top - top2

    if top >= min_fill:
        if gap < delta:
            return "multi", top_idx, top, top2
        return "ok", top_idx, top, top2

    # top < min_fill: borderline single olabilir mi?
    if top >= 0.85 * min_fill and gap >= delta:
        return "borderline", top_idx, top, top2

    return "blank", top_idx, top, top2


def read_grid(th_inv: np.ndarray, grid: Dict[str, Any], roi_r: int,
             min_fill: float, delta: float,
             force_multi_if_two_strong: bool = False) -> Tuple[str, List[Dict[str, Any]]]:

    ax, ay = grid["anchor"]["x"], grid["anchor"]["y"]
    dx, dy = grid["dx"], grid["dy"]
    cols, rows = grid["cols"], grid["rows"]
    labels = grid["row_labels"]

    digits: List[str] = []
    debug: List[Dict[str, Any]] = []

    for c in range(cols):
        scores: List[float] = []
        for r in range(rows):
            cx = ax + c * dx
            cy = ay + r * dy
            scores.append(bubble_score(th_inv, cx, cy, roi_r))

        status, top_idx, top, top2 = _decide_from_scores(scores, min_fill=min_fill, delta=delta)

        # Generic: if two strong marks, force multi (use for student_no and class_code)
        if force_multi_if_two_strong and top >= min_fill and top2 >= min_fill:
            status = "multi"

        if status == "blank":
            value = "?"
        elif status == "multi":
            value = "!"
        else:
            value = str(labels[top_idx])

        digits.append(value)

        debug.append({
            "col": c + 1,
            "top": round(top, 3),
            "second": round(top2, 3),
            "confidence": round(top - top2, 3),
            "status": status
        })

    return "".join(digits), debug


def read_row(th_inv: np.ndarray, row: Dict[str, Any], roi_r: int, min_fill: float, delta: float) -> Tuple[str, Dict[str, Any]]:
    """
    Read a single-choice row like Booklet type (A/B/C/D).
    """
    ax, ay = row["anchor"]["x"], row["anchor"]["y"]
    dx = row["dx"]
    labels = row["labels"]

    scores = []
    for i in range(len(labels)):
        cx = ax + i * dx
        cy = ay
        scores.append(bubble_score(th_inv, cx, cy, roi_r))

    status, top_idx, top, top2 = _decide_from_scores(scores, min_fill=min_fill, delta=delta)

    if top >= min_fill and top2 >= min_fill:
        status = "multi"

    if status == "blank":
        value = "?"
    elif status == "multi":
        value = "!"
    else:
        value = labels[top_idx]

    dbg = {
        "scores": [round(s, 3) for s in scores],
        "top": round(top, 3),
        "second": round(top2, 3),
        "confidence": round(top - top2, 3),
        "status": status
    }
    return value, dbg


from typing import Dict, Any, List, Tuple
import numpy as np

def read_answers(
    th_inv: np.ndarray,
    ans: Dict[str, Any],
    roi_r: int,
    min_fill: float,
    delta: float,
    num_items: int = 0
) -> Tuple[List[str], List[Dict[str, Any]]]:
    """
    Read answers: rows=questions, cols=choices.
    num_items > 0 ise sadece o kadar satir okunur, 0 ise tumu okunur.
    Output per question:
      - ""   : blank (no confident mark)
      - "!"  : multi (2+ strong marks OR ambiguous by delta)
      - "A"-"E": single choice
    """
    ax, ay = ans["anchor"]["x"], ans["anchor"]["y"]
    dx, dy = ans["dx"], ans["dy"]
    rows, cols = ans["rows"], ans["cols"]
    col_labels = ans["col_labels"]

    if num_items > 0:
        rows = min(rows, num_items)

    out: List[str] = []
    dbg: List[Dict[str, Any]] = []

    for q in range(rows):
        scores: List[float] = []
        for c in range(cols):
            cx = ax + c * dx
            cy = ay + q * dy
            scores.append(bubble_score(th_inv, cx, cy, roi_r))

        status, top_idx, top, top2 = _decide_from_scores(scores, min_fill=min_fill, delta=delta)

        # Answers: if two strong marks exist, force multi (captures real double-mark cases)
        if top >= min_fill and top2 >= min_fill:
            status = "multi"

        if status == "blank":
            value = ""
        elif status == "multi":
            value = "!"
        else:
            # "ok" veya "borderline" -> en koyu harf
            value = col_labels[top_idx]

        out.append(value)

        dbg.append({
            "q": q + 1,
            "scores": [round(s, 3) for s in scores],
            "top": round(top, 3),
            "second": round(top2, 3),
            "confidence": round(top - top2, 3),
            "status": status,
            "value": value
        })

    return out, dbg


def read_seating(th_inv: np.ndarray, seating: Dict[str, Any], roi_r: int, min_fill: float, delta: float) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
    """
    Read seating selection (single mark) from grid_explicit.

    Expected JSON:
      seating = {"type":"grid_explicit", "cells":[{"id":"A1","x":..,"y":..}, ...]}

    Returns:
      seating_result:
        - {"cell_id": "<ID>", "status":"ok"}  when confident
        - None                                 when blank or ambiguous
      seating_debug:
        - includes top cell id, top/second/confidence/status
    """
    cells = seating.get("cells", [])
    if not cells:
        return None, {"status": "disabled_or_empty"}

    scores: List[float] = []
    labels: List[str] = []
    coords: List[Tuple[float, float]] = []

    for c in cells:
        cid = str(c.get("id", "cell"))
        x = float(c["x"]); y = float(c["y"])
        labels.append(cid)
        coords.append((x, y))
        scores.append(bubble_score(th_inv, x, y, roi_r))

    status, top_idx, top, top2 = _decide_from_scores(scores, min_fill=min_fill, delta=delta)
    gap = top - top2

    top_id = labels[top_idx] if labels else None
    top_x, top_y = coords[top_idx] if coords else (None, None)

    seating_result: Optional[Dict[str, Any]] = None
    if status == "ok":
        seating_result = {"cell_id": top_id, "status": "ok"}

    dbg = {
        "top_id": top_id,
        "top_x": round(float(top_x), 2) if top_x is not None else None,
        "top_y": round(float(top_y), 2) if top_y is not None else None,
        "top": round(top, 3),
        "second": round(top2, 3),
        "confidence": round(gap, 3),
        "status": status,
        "top_index": int(top_idx)
    }
    return seating_result, dbg


def draw_overlay(warped: np.ndarray, m: Dict[str, Any], th_inv: np.ndarray,
                 adaptive: Optional[Dict[str, Any]] = None,
                 num_items: int = 0) -> np.ndarray:
    """
    Problems-only overlay per your rules:

    Student No / Class Code:
      - blank => draw all 10 bubbles (red)
      - multi => draw only marked bubbles (score >= min_fill) (red)
      - ok    => draw nothing

    Booklet:
      - blank => draw all 4 bubbles (red)
      - multi => draw only marked bubbles (score >= min_fill) (red)
      - ok    => draw nothing

    Answers:
      - blank => draw all 5 bubbles (red)
      - multi => draw only marked bubbles (score >= min_fill) (red)
      - ok    => draw nothing
    """
    out = warped.copy()
    r = int(m["bubble"]["roi_radius_px"])

    # Resolve thresholds: adaptive if provided, else static defaults
    mf_booklet = adaptive["min_fill_booklet"] if adaptive else MIN_FILL_BOOKLET
    mf_student_no = adaptive["min_fill_student_no"] if adaptive else MIN_FILL_STUDENT_NO
    mf_class_code = adaptive["min_fill_class_code"] if adaptive else MIN_FILL_CLASS_CODE
    mf_answers = adaptive["min_fill_answers"] if adaptive else MIN_FILL_ANSWERS
    d_student_no = adaptive["delta_student_no"] if adaptive else DELTA_STUDENT_NO
    d_general = adaptive["delta"] if adaptive else DELTA

    def draw_red(cx: float, cy: float, thickness: int = 2):
        cv2.circle(out, (int(cx), int(cy)), r, (0, 0, 255), thickness)

    # ----------------
    # Helper: compute scores for a grid column (rows=10)
    # ----------------
    def column_scores(ax, ay, dx, dy, col_idx, rows):
        s = []
        for rr in range(rows):
            cx = ax + col_idx * dx
            cy = ay + rr * dy
            s.append(bubble_score(th_inv, cx, cy, r))
        return s

    # ----------------
    # BOOKLET (row)
    # ----------------
    book = m["booklet"]
    bx, by = book["anchor"]["x"], book["anchor"]["y"]
    bdx = book["dx"]
    blabels = book["labels"]

    b_scores = []
    for i in range(len(blabels)):
        cx = bx + i * bdx
        cy = by
        b_scores.append(bubble_score(th_inv, cx, cy, r))

    b_status, b_top_idx, b_top, b_top2 = _decide_from_scores(b_scores, mf_booklet, d_general)

    # 2-strong rule (same as your read_row)
    if b_top >= mf_booklet and b_top2 >= mf_booklet:
        b_status = "multi"

    if b_status == "blank":
        for i in range(len(blabels)):
            draw_red(bx + i * bdx, by)
    elif b_status == "multi":
        for i, s in enumerate(b_scores):
            if s >= mf_booklet:
                draw_red(bx + i * bdx, by)

    # ----------------
    # STUDENT NO (grid: 12 cols x 10 rows)
    # ----------------
    sn = m["student_no"]
    sn_ax, sn_ay = sn["anchor"]["x"], sn["anchor"]["y"]
    sn_dx, sn_dy = sn["dx"], sn["dy"]
    sn_cols, sn_rows = sn["cols"], sn["rows"]

    for c in range(sn_cols):
        scores = column_scores(sn_ax, sn_ay, sn_dx, sn_dy, c, sn_rows)
        status, top_idx, top, top2 = _decide_from_scores(scores, mf_student_no, d_student_no)

        # student_no: 2-strong rule (same as your read_grid usage)
        if top >= mf_student_no and top2 >= mf_student_no:
            status = "multi"

        if status == "blank":
            # draw all 10 bubbles
            for rr in range(sn_rows):
                draw_red(sn_ax + c * sn_dx, sn_ay + rr * sn_dy)
        elif status == "multi":
            # draw only marked bubbles
            for rr, s in enumerate(scores):
                if s >= mf_student_no:
                    draw_red(sn_ax + c * sn_dx, sn_ay + rr * sn_dy)

    # ----------------
    # CLASS CODE (grid: 4 cols x 10 rows)
    # ----------------
    cc = m["class_code"]
    cc_ax, cc_ay = cc["anchor"]["x"], cc["anchor"]["y"]
    cc_dx, cc_dy = cc["dx"], cc["dy"]
    cc_cols, cc_rows = cc["cols"], cc["rows"]

    for c in range(cc_cols):
        scores = column_scores(cc_ax, cc_ay, cc_dx, cc_dy, c, cc_rows)
        status, top_idx, top, top2 = _decide_from_scores(scores, mf_class_code, d_general)

        # class_code: 2-strong rule (as you wanted)
        if top >= mf_class_code and top2 >= mf_class_code:
            status = "multi"

        if status == "blank":
            for rr in range(cc_rows):
                draw_red(cc_ax + c * cc_dx, cc_ay + rr * cc_dy)
        elif status == "multi":
            for rr, s in enumerate(scores):
                if s >= mf_class_code:
                    draw_red(cc_ax + c * cc_dx, cc_ay + rr * cc_dy)

    # ----------------
    # ANSWERS (grid: num_items rows x 5 cols)
    # ----------------
    ans = m["answers"]
    a_ax, a_ay = ans["anchor"]["x"], ans["anchor"]["y"]
    a_dx, a_dy = ans["dx"], ans["dy"]
    a_rows, a_cols = ans["rows"], ans["cols"]
    if num_items > 0:
        a_rows = min(a_rows, num_items)

    for q in range(a_rows):
        scores = []
        for c in range(a_cols):
            cx = a_ax + c * a_dx
            cy = a_ay + q * a_dy
            scores.append(bubble_score(th_inv, cx, cy, r))

        status, top_idx, top, top2 = _decide_from_scores(scores, mf_answers, d_general)

        # answers: 2-strong rule (the one we just agreed)
        if top >= mf_answers and top2 >= mf_answers:
            status = "multi"

        if status == "blank":
            # draw all 5 bubbles
            for c in range(a_cols):
                draw_red(a_ax + c * a_dx, a_ay + q * a_dy)
        elif status == "multi":
            # draw only marked bubbles
            for c, s in enumerate(scores):
                if s >= mf_answers:
                    draw_red(a_ax + c * a_dx, a_ay + q * a_dy)

    return out


def main(image_path: str, map_path: str, out_json: str = "result.json", out_overlay: str = "overlay.png"):
    m = load_map(map_path)

    img = cv2.imread(image_path)
    if img is None:
        raise RuntimeError(f"Cannot read image: {image_path}")

    warped, _, _ = warp_to_reference(img, m["alignment"])
    th_inv = prep_binary(warped)

    roi_r = int(m["bubble"]["roi_radius_px"])

    # Pass 1: quick read to check alignment quality
    pre_scores = collect_all_bubble_scores(th_inv, m, roi_r)
    pre_adaptive = compute_adaptive_thresholds(pre_scores)
    pre_sno, _ = read_grid(th_inv, m["student_no"], roi_r,
                           pre_adaptive["min_fill_student_no"],
                           pre_adaptive["delta_student_no"],
                           force_multi_if_two_strong=True)

    # Alignment correction: only if student_no has read errors
    if "?" in pre_sno or "!" in pre_sno:
        align_ox, align_oy = compute_alignment_correction(th_inv, m)
        if align_ox != 0 or align_oy != 0:
            m = apply_offset_to_map(m, align_ox, align_oy)
            print(f"Alignment correction: dx={align_ox}, dy={align_oy}")

    # Pass 2: full read (with potentially corrected map)
    all_scores = collect_all_bubble_scores(th_inv, m, roi_r)
    adaptive = compute_adaptive_thresholds(all_scores)

    student_no, st_dbg = read_grid( th_inv, m["student_no"], roi_r, adaptive["min_fill_student_no"], adaptive["delta_student_no"], force_multi_if_two_strong=True)
    class_code, cc_dbg = read_grid( th_inv, m["class_code"], roi_r, adaptive["min_fill_class_code"], adaptive["delta"], force_multi_if_two_strong=True)
    booklet, b_dbg = read_row(th_inv, m["booklet"], roi_r, adaptive["min_fill_booklet"], adaptive["delta"])
    answers, a_dbg = read_answers(th_inv, m["answers"], roi_r, adaptive["min_fill_answers"], adaptive["delta"])

    seating_result = None
    seating_dbg = None
    if "seating" in m and m["seating"].get("type") == "grid_explicit":
        seating_result, seating_dbg = read_seating(th_inv, m["seating"], roi_r, adaptive["min_fill_seating"], adaptive["delta"])

    result: Dict[str, Any] = {
        "student_no": student_no,
        "class_code": class_code,
        "booklet": booklet,
        "answers": answers,
        "seating": seating_result,
        "debug": {
            "student_no": st_dbg,
            "class_code": cc_dbg,
            "booklet": b_dbg,
            "answers": a_dbg,
            "seating": seating_dbg,
            "adaptive_thresholds": adaptive
        }
    }

    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    overlay = draw_overlay(warped, m, th_inv, adaptive=adaptive)
    cv2.imwrite(out_overlay, overlay)
    print(f"OK -> {out_json}, {out_overlay}")


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 3:
        print("Usage: python omr.py <filled_form_image> <bubble_map_v1.json>")
        sys.exit(1)
    main(sys.argv[1], sys.argv[2])
