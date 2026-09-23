"""
Excel Yukleme (SIM-14)
======================
`.xlsx` dosyasindan sinav yaniti + oturma + anahtar okur, normalize
eder, sıkı doğrulama yapar, `ExamData`'ya cevirir. Mevcut `analyze_exam`
akisi degismez — Excel'den gelen veri optik okumadan gelenle **ayni**
`ExamData` nesnesine donusur.

Dosya yapisi
------------
3 zorunlu sayfa (Turkce sabit isim):
  - `Yanitlar`             : ogrenci_no, ad_soyad?, salon?, oturma_kodu?,
                             gozetmen_onayi?, kitapcik?, S1..Sn
  - `Anahtar`              : madde_no, dogru_cevap
  - `Kitapcik_Eslestirme`  : kitapcik, pozisyon, madde_no
                             (kitapcik > 1 ise ZORUNLU)

Yanıt normalize
---------------
- Harf (A-E) veya rakam (1-5): ikisi de kabul; icte 1..n_options
- Buyuk/kucuk harf duyarsiz, bosluk temizlenir
- ASCII disi (ornegin Kiril a) reddedilir → hata
- Boş → 0 (bos yanit)
- Coklu isaret ("AB", "A,B", ">>>") → -1

Doğrulama
---------
Engelleyici hatalar (analiz baslamaz):
  - ogrenci_no tekrari
  - Zorunlu sutun eksik
  - Madde sutunu bulunamadi
  - Anahtar uzunlugu != madde sayisi
  - Anahtar veya yanitlarda gecersiz secenek
  - Kitapcik > 1 ama eslestirme yok
  - Eslestirme tutarsizligi

Uyarilar (analiz calisir):
  - Oturma cakismasi, format hatasi, dusuk kapsam
  - Tamamen bos satirlar (dislanır)
  - Olu maddeler
  - Gozetmen onayi olmayan kayıtlar
"""

from __future__ import annotations

import io
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

# Excel okuma icin openpyxl (pandas yerine dogrudan — hucre tipini
# koruyarak daha guvenli)
try:
    from openpyxl import load_workbook
except ImportError as e:
    raise ImportError("openpyxl gerekli: pip install openpyxl") from e


# ── Sabitler ──────────────────────────────────────────────

SHEET_YANITLAR = "Yanitlar"
SHEET_ANAHTAR = "Anahtar"
SHEET_KITAPCIK = "Kitapcik_Eslestirme"

MAX_ROWS = 5000  # spec §7 satir limiti

_ITEM_COL_RE = re.compile(r"^\s*S\s*(\d+)\s*$", re.IGNORECASE)


@dataclass
class ExcelValidationResult:
    """Excel dosyasinin dogrulama sonucu.

    engelleyici hata varsa `ok = False`, ExamData uretilmez.
    """
    ok: bool = True
    blocking_errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    # Onizleme bilgileri
    n_students: int = 0
    n_items: int = 0
    n_options: int = 0
    n_booklets: int = 0
    n_halls: int = 0
    seat_coverage: float = 0.0
    seat_filter_active: bool = False
    preview_rows: List[Dict[str, Any]] = field(default_factory=list)
    # Aciklama
    source: str = "excel"


@dataclass
class ExcelReadResult:
    """Excel dosyasinin okunmus/normalize edilmis hali."""
    validation: ExcelValidationResult
    exam_data: Optional[Any] = None  # ExamData (validation.ok ise dolu)
    student_meta: List[Dict[str, Any]] = field(default_factory=list)


# ── Yardimcilar ──────────────────────────────────────────

def _cell_str(v: Any) -> str:
    """Hucreyi string'e cevir, strip. None → ''."""
    if v is None:
        return ""
    if isinstance(v, float):
        if v.is_integer():
            return str(int(v))
        return str(v)
    return str(v).strip()


def _normalize_answer(raw: Any, n_options: int) -> int:
    """Yaniti kanonik forma cevir. Doner:
       0  → bos
      -1  → coklu/gecersiz
      1..n_options → gecerli secim
    ASCII disi karakter → ValueError (caller tarafinda hata olarak yakalanir)
    """
    if raw is None:
        return 0
    s = str(raw).strip()
    if not s:
        return 0
    if not s.isascii():
        raise ValueError(f"ASCII disi karakter: {s!r}")
    # Coklu isaret desenler
    if any(sep in s for sep in (",", ";", "|", "/", " ")):
        return -1
    if len(s) > 1:
        # Coklu rakam olabilir mi? "10" → 10 (n_options destekliyorsa)
        if s.isdigit():
            v = int(s)
            return v if 1 <= v <= n_options else -1
        # "AB", "**" gibi — coklu
        return -1
    c = s.upper()
    if c.isdigit():
        v = int(c)
        return v if 1 <= v <= n_options else -1
    if "A" <= c <= "Z":
        idx = ord(c) - ord("A") + 1
        return idx if 1 <= idx <= n_options else -1
    return -1  # bilinmeyen tek karakter → gecersiz


def _normalize_bool(raw: Any) -> Optional[bool]:
    """gozetmen_onayi normalizasyonu: E/H, 1/0, TRUE/FALSE → bool | None."""
    if raw is None:
        return None
    s = str(raw).strip().upper()
    if not s:
        return None
    if s in ("E", "EVET", "1", "TRUE", "T", "Y", "YES"):
        return True
    if s in ("H", "HAYIR", "0", "FALSE", "F", "N", "NO"):
        return False
    return None


def _detect_n_options(answers_flat: List[int], key_flat: List[int]) -> int:
    """Yanit ve anahtardaki 1..n_options araligindan n_options tespit et."""
    valid = [v for v in answers_flat + key_flat if v >= 1]
    if not valid:
        return 5  # default
    return max(4, max(valid))  # en az 4 secenek


# ── Ana okuyucu ──────────────────────────────────────────

def read_excel(file_bytes: bytes) -> ExcelReadResult:
    """`.xlsx` binary'sini oku, normalize et, validate et.

    Doner: ExcelReadResult
      validation.ok == True → exam_data dolu
      validation.ok == False → blocking_errors dolu
    """
    val = ExcelValidationResult()
    try:
        wb = load_workbook(io.BytesIO(file_bytes), data_only=True,
                             read_only=True)
    except Exception as e:  # noqa: BLE001
        val.ok = False
        val.blocking_errors.append(f"Excel dosyasi okunamadi: {e}")
        return ExcelReadResult(validation=val)

    # Sayfa varligi
    sheet_names = wb.sheetnames
    if SHEET_YANITLAR not in sheet_names:
        val.blocking_errors.append(
            f"'{SHEET_YANITLAR}' sayfasi bulunamadi. "
            f"Mevcut sayfalar: {sheet_names}")
    if SHEET_ANAHTAR not in sheet_names:
        val.blocking_errors.append(
            f"'{SHEET_ANAHTAR}' sayfasi bulunamadi.")
    if val.blocking_errors:
        val.ok = False
        return ExcelReadResult(validation=val)

    # === Anahtar sayfasi ===
    ws_key = wb[SHEET_ANAHTAR]
    key_rows: List[Tuple[int, Any]] = []
    header: Optional[List[str]] = None
    for r_idx, row in enumerate(ws_key.iter_rows(values_only=True), start=1):
        if header is None:
            header = [_cell_str(v).lower() for v in row]
            if "madde_no" not in header or "dogru_cevap" not in header:
                val.blocking_errors.append(
                    f"'{SHEET_ANAHTAR}' basliklari: 'madde_no' ve "
                    f"'dogru_cevap' olmali. Bulundu: {header}")
                val.ok = False
                return ExcelReadResult(validation=val)
            i_mno = header.index("madde_no")
            i_ans = header.index("dogru_cevap")
            continue
        if all(v is None for v in row):
            continue
        try:
            mno = int(_cell_str(row[i_mno]))
            key_rows.append((mno, row[i_ans]))
        except (ValueError, IndexError):
            val.blocking_errors.append(
                f"'{SHEET_ANAHTAR}' satir {r_idx}: madde_no sayi degil")

    if not key_rows:
        val.blocking_errors.append(f"'{SHEET_ANAHTAR}' bos")
        val.ok = False
        return ExcelReadResult(validation=val)

    key_rows.sort(key=lambda x: x[0])
    n_items = len(key_rows)
    # Numaralar 1..n olmali
    expected = list(range(1, n_items + 1))
    actual = [k[0] for k in key_rows]
    if actual != expected:
        val.blocking_errors.append(
            f"'{SHEET_ANAHTAR}' madde_no 1..{n_items} olmali; "
            f"aldik: {actual[:10]}...")
        val.ok = False
        return ExcelReadResult(validation=val)

    # === Yanitlar sayfasi ===
    ws_yan = wb[SHEET_YANITLAR]
    yan_rows_iter = ws_yan.iter_rows(values_only=True)
    try:
        header_yan = [_cell_str(v).lower()
                        for v in next(yan_rows_iter)]
    except StopIteration:
        val.blocking_errors.append(f"'{SHEET_YANITLAR}' bos")
        val.ok = False
        return ExcelReadResult(validation=val)

    if "ogrenci_no" not in header_yan:
        val.blocking_errors.append(
            f"'{SHEET_YANITLAR}' 'ogrenci_no' sutunu zorunlu")
        val.ok = False
        return ExcelReadResult(validation=val)

    # Madde sutunlarini tespit et (S1, S2, ...)
    item_cols: List[Tuple[int, int]] = []  # (col_idx, item_no)
    for i, h in enumerate(header_yan):
        m = _ITEM_COL_RE.match(h)
        if m:
            item_cols.append((i, int(m.group(1))))
    if not item_cols:
        val.blocking_errors.append(
            f"'{SHEET_YANITLAR}' madde sutunu bulunamadi (S1, S2, ... deseni)")
        val.ok = False
        return ExcelReadResult(validation=val)
    item_cols.sort(key=lambda x: x[1])
    n_positions = len(item_cols)

    idx_ogr = header_yan.index("ogrenci_no")
    idx_ad = header_yan.index("ad_soyad") if "ad_soyad" in header_yan else -1
    idx_salon = header_yan.index("salon") if "salon" in header_yan else -1
    idx_seat = header_yan.index("oturma_kodu") if "oturma_kodu" in header_yan else -1
    idx_gozet = (header_yan.index("gozetmen_onayi")
                  if "gozetmen_onayi" in header_yan else -1)
    idx_kit = header_yan.index("kitapcik") if "kitapcik" in header_yan else -1

    # Satirlari topla
    students: List[Dict[str, Any]] = []
    n_ascii_errors = 0
    for r_idx, row in enumerate(yan_rows_iter, start=2):
        if all(v is None for v in row):
            continue
        if len(students) >= MAX_ROWS:
            val.blocking_errors.append(
                f"Satir limiti asildi ({MAX_ROWS}); dosyayi bolun")
            val.ok = False
            return ExcelReadResult(validation=val)
        try:
            ogr = _cell_str(row[idx_ogr])
        except IndexError:
            continue
        if not ogr:
            val.warnings.append(f"Satir {r_idx}: ogrenci_no bos, atlandı")
            continue

        raw_answers: List[int] = []
        for col_i, _item_no in item_cols:
            try:
                raw = row[col_i] if col_i < len(row) else None
                normalized = _normalize_answer(raw, n_options=999)  # placeholder
                raw_answers.append(normalized)
            except ValueError as ve:
                n_ascii_errors += 1
                if n_ascii_errors <= 5:
                    val.blocking_errors.append(
                        f"Satir {r_idx}, S{_item_no}: {ve}")
                raw_answers.append(-1)

        students.append({
            "ogrenci_no": ogr,
            "ad_soyad": _cell_str(row[idx_ad]) if idx_ad >= 0 else "",
            "salon": _cell_str(row[idx_salon]) if idx_salon >= 0 else "",
            "oturma_kodu": _cell_str(row[idx_seat]) if idx_seat >= 0 else "",
            "gozetmen_onayi": _normalize_bool(row[idx_gozet])
                                if idx_gozet >= 0 else None,
            "kitapcik": _cell_str(row[idx_kit]) if idx_kit >= 0 else "",
            "answers_raw": raw_answers,  # placeholder, n_options ile yeniden normalize
            "row_no": r_idx,
        })

    if n_ascii_errors > 5:
        val.blocking_errors.append(
            f"... ve {n_ascii_errors - 5} ASCII disi karakter daha")

    if not students:
        val.blocking_errors.append(f"'{SHEET_YANITLAR}' bos veya tamamı hatalı")
        val.ok = False
        return ExcelReadResult(validation=val)

    # ogrenci_no tekrari
    seen = set()
    dupes: List[str] = []
    for s in students:
        if s["ogrenci_no"] in seen:
            dupes.append(s["ogrenci_no"])
        seen.add(s["ogrenci_no"])
    if dupes:
        val.blocking_errors.append(
            f"ogrenci_no tekrari: {dupes[:5]}{'...' if len(dupes) > 5 else ''}")
        val.ok = False

    # === Kitapcik eslestirme ===
    booklets = sorted(set(s["kitapcik"] for s in students if s["kitapcik"]))
    if not booklets:
        booklets = ["1"]
        for s in students:
            s["kitapcik"] = "1"
    n_booklets = len(booklets)
    if n_booklets > 1:
        if SHEET_KITAPCIK not in sheet_names:
            val.blocking_errors.append(
                f"{n_booklets} kitapçık var ama '{SHEET_KITAPCIK}' "
                f"sayfası yok")
            val.ok = False
            return ExcelReadResult(validation=val)
        perm_map = _read_permutation(wb[SHEET_KITAPCIK], booklets,
                                       n_positions, val)
        if perm_map is None:
            val.ok = False
            return ExcelReadResult(validation=val)
    else:
        perm_map = {booklets[0]: list(range(n_positions))}

    if val.blocking_errors:
        val.ok = False
        return ExcelReadResult(validation=val)

    # Anahtardan n_options tespit et
    tmp_key_normalized: List[int] = []
    for _mno, ans in key_rows:
        try:
            v = _normalize_answer(ans, n_options=999)  # placeholder
            tmp_key_normalized.append(v if v > 0 else 0)
        except ValueError as ve:
            val.blocking_errors.append(f"Anahtar: {ve}")
    all_answers_flat: List[int] = []
    for s in students:
        all_answers_flat.extend(a for a in s["answers_raw"] if a > 0)
    n_options = _detect_n_options(all_answers_flat, tmp_key_normalized)
    # Sinirla — cok yuksek n_options genelde hata isaretidir
    if n_options > 10:
        val.blocking_errors.append(
            f"Tespit edilen secenek sayisi cok yüksek ({n_options}) — "
            f"muhtemelen yanit formati hatalı")
        val.ok = False

    # Anahtari yeniden normalize et (dogru n_options ile)
    key_normalized: List[int] = []
    for mno, ans in key_rows:
        try:
            v = _normalize_answer(ans, n_options)
            if v < 1 or v > n_options:
                val.blocking_errors.append(
                    f"Anahtar madde {mno}: gecersiz secim {ans!r}")
                v = 1
        except ValueError:
            v = 1
        key_normalized.append(v)

    # Yanitlari yeniden normalize et (dogru n_options ile)
    responses_arr = np.zeros((len(students), n_positions), dtype=np.int8)
    for si, s in enumerate(students):
        for pi, raw_v in enumerate(s["answers_raw"]):
            if raw_v == 0 or raw_v == -1:
                responses_arr[si, pi] = raw_v
                continue
            # raw_v > 0 → n_options yeniden dogruladıktan sonra clamp
            if raw_v > n_options:
                responses_arr[si, pi] = -1
            else:
                responses_arr[si, pi] = raw_v

    if val.blocking_errors:
        val.ok = False
        return ExcelReadResult(validation=val)

    # === Uyarilar ===
    _check_warnings(val, students, responses_arr, key_normalized)

    # ExamData olustur
    from kopya.engine.core import ExamData
    booklet_idx = {b: i for i, b in enumerate(booklets)}
    booklet_arr = np.array([booklet_idx[s["kitapcik"]] for s in students],
                            dtype=np.int32)
    student_ids = np.array([s["ogrenci_no"] for s in students],
                             dtype=object)
    seat_codes = np.array([s["oturma_kodu"] for s in students], dtype=object)
    halls = np.array([s["salon"] for s in students], dtype=object)
    proctor = np.array([s["gozetmen_onayi"] for s in students], dtype=object)

    # Permutasyon matrisi (n_booklets, n_positions)
    perm_arr = np.zeros((n_booklets, n_positions), dtype=np.int32)
    for b_id, perm_list in perm_map.items():
        b_i = booklet_idx[b_id]
        perm_arr[b_i] = np.array(perm_list, dtype=np.int32)

    exam_data = ExamData(
        responses=responses_arr,
        key=np.array(key_normalized, dtype=np.int8),
        booklet=booklet_arr,
        permutation=perm_arr,
        student_id=student_ids,
        n_options=n_options,
        seat_code=seat_codes if any(seat_codes) else None,
        hall=halls if any(halls) else None,
        proctor_verified=(proctor.astype(bool)
                           if any(p is not None for p in proctor)
                           else None),
    )

    # Onizleme
    val.n_students = len(students)
    val.n_items = n_items
    val.n_options = n_options
    val.n_booklets = n_booklets
    val.n_halls = len(set(s["salon"] for s in students if s["salon"]))
    n_with_seat = sum(1 for s in students if s["oturma_kodu"])
    val.seat_coverage = n_with_seat / len(students) if students else 0.0
    from kopya.engine._neighbor import DEFAULT_COVERAGE_THRESHOLD
    val.seat_filter_active = val.seat_coverage >= DEFAULT_COVERAGE_THRESHOLD
    val.preview_rows = [
        {k: v for k, v in s.items() if k != "answers_raw"}
        for s in students[:10]
    ]

    return ExcelReadResult(validation=val, exam_data=exam_data,
                            student_meta=[
                                {"ogrenci_no": s["ogrenci_no"],
                                 "ad_soyad": s["ad_soyad"]}
                                for s in students])


def _read_permutation(ws, booklets: List[str], n_positions: int,
                        val: ExcelValidationResult) -> Optional[Dict[str, List[int]]]:
    """Kitapcik_Eslestirme sayfasindan permutasyon tablosu. tutarsizsa None."""
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        val.blocking_errors.append(f"'{SHEET_KITAPCIK}' bos")
        return None
    header = [_cell_str(v).lower() for v in rows[0]]
    for needed in ("kitapcik", "pozisyon", "madde_no"):
        if needed not in header:
            val.blocking_errors.append(
                f"'{SHEET_KITAPCIK}' '{needed}' sutunu eksik")
            return None
    i_k = header.index("kitapcik")
    i_p = header.index("pozisyon")
    i_m = header.index("madde_no")

    perm_map: Dict[str, Dict[int, int]] = {b: {} for b in booklets}
    for r_idx, row in enumerate(rows[1:], start=2):
        if all(v is None for v in row):
            continue
        b = _cell_str(row[i_k])
        if b not in perm_map:
            val.warnings.append(
                f"'{SHEET_KITAPCIK}' satir {r_idx}: bilinmeyen kitapcik {b}")
            continue
        try:
            pos = int(_cell_str(row[i_p]))
            mno = int(_cell_str(row[i_m]))
        except ValueError:
            val.blocking_errors.append(
                f"'{SHEET_KITAPCIK}' satir {r_idx}: pozisyon/madde_no "
                f"sayi degil")
            return None
        if not (1 <= pos <= n_positions):
            val.blocking_errors.append(
                f"'{SHEET_KITAPCIK}' satir {r_idx}: pozisyon {pos} "
                f"1..{n_positions} disi")
            return None
        if not (1 <= mno <= n_positions):
            val.blocking_errors.append(
                f"'{SHEET_KITAPCIK}' satir {r_idx}: madde_no {mno} "
                f"1..{n_positions} disi")
            return None
        if pos in perm_map[b]:
            val.blocking_errors.append(
                f"'{SHEET_KITAPCIK}': kitapcik {b} pozisyon {pos} birden "
                f"fazla tanimli")
            return None
        perm_map[b][pos] = mno

    result: Dict[str, List[int]] = {}
    for b, pmap in perm_map.items():
        if len(pmap) != n_positions:
            val.blocking_errors.append(
                f"'{SHEET_KITAPCIK}': kitapcik {b} icin {n_positions} "
                f"pozisyon bekleniyordu, {len(pmap)} tanimli")
            return None
        # Her pozisyon icin 1'den n'e madde_no. permutation[b, pos-1] = mno-1
        arr = [pmap[p] - 1 for p in range(1, n_positions + 1)]
        # Set: her madde_no 0..n-1 arasi tam permutasyon?
        if sorted(arr) != list(range(n_positions)):
            val.blocking_errors.append(
                f"'{SHEET_KITAPCIK}': kitapcik {b} tam permutasyon degil")
            return None
        result[b] = arr
    return result


def _check_warnings(val: ExcelValidationResult,
                     students: List[Dict[str, Any]],
                     responses: np.ndarray,
                     key: List[int]) -> None:
    """Uyarilari topla (analiz calisir, kullanici bilgilendirilir)."""
    # Bos satirlar (tumu 0) — analizden cikarilir mi? Şimdilik sadece uyar.
    empty_rows = int((responses == 0).all(axis=1).sum())
    if empty_rows > 0:
        val.warnings.append(
            f"{empty_rows} satirin tamami bos (yine de analize dahil)")

    # Olu maddeler (herkes dogru veya hepsi bos)
    dead_items = 0
    for j in range(responses.shape[1]):
        col = responses[:, j]
        # Herkes dogru?
        n_correct = int((col == key[j]).sum())
        n_empty = int((col == 0).sum())
        if n_correct == responses.shape[0]:
            dead_items += 1
        elif n_empty == responses.shape[0]:
            dead_items += 1
    if dead_items > 0:
        val.warnings.append(
            f"{dead_items} olu madde (herkes ayni cevap veya hepsi bos)")

    # Gozetmen onayi yok
    n_no_proctor = sum(1 for s in students if not s["gozetmen_onayi"])
    if n_no_proctor > 0:
        val.warnings.append(
            f"{n_no_proctor} kayitta gozetmen onayi yok")

    # Oturma cakisma / format kontrolleri — Excel katmaninda saf sayimla
    from kopya.engine._neighbor import parse_seat_label, DEFAULT_COVERAGE_THRESHOLD
    seat_collisions: Dict[Tuple[str, Tuple[int, int]], List[str]] = {}
    parse_err: List[str] = []
    for s in students:
        code = s["oturma_kodu"]
        if not code:
            continue
        p = parse_seat_label(code)
        if p is None:
            parse_err.append(f"{s['ogrenci_no']}='{code}'")
            continue
        h = s["salon"] or None
        key_s = (h or "", p)
        seat_collisions.setdefault(key_s, []).append(s["ogrenci_no"])
    n_coll = sum(1 for members in seat_collisions.values() if len(members) > 1)
    if n_coll > 0:
        examples = []
        for (h, seat), members in seat_collisions.items():
            if len(members) > 1:
                seat_str = f"{chr(ord('A') + seat[0] - 1)}{seat[1]}"
                examples.append(f"{h}::{seat_str}: {', '.join(members[:3])}")
                if len(examples) >= 3:
                    break
        val.warnings.append(
            f"{n_coll} koltuk cakisma tespit edildi: {'; '.join(examples)}")
    if parse_err:
        val.warnings.append(
            f"{len(parse_err)} oturma kodu format hatasi: "
            f"{'; '.join(parse_err[:5])}")

    # Kapsam
    n_with_seat = sum(1 for s in students if s["oturma_kodu"])
    cov = n_with_seat / len(students) if students else 0.0
    if 0 < cov < DEFAULT_COVERAGE_THRESHOLD:
        val.warnings.append(
            f"Oturma kapsamı %{cov*100:.0f} — {int(DEFAULT_COVERAGE_THRESHOLD*100)}% "
            f"altında; oturma filtresi devre disi kalacak")


__all__ = [
    "ExcelValidationResult",
    "ExcelReadResult",
    "read_excel",
    "MAX_ROWS",
]
