"""
Kayıt listesi / kayıt detay / düzenleme view'ları (sihirbaz 4. adım).

Kaynak: omr_analysis/routes.py
- test_records          ← test_records_page       (2739)
- batch_detail          ← batch_detail / batch_records (3619 / 4361; ikisi de
                          kayıt listesine yönlendirir)
- record_delete         ← delete_record_endpoint  (4373)
- delete_selected       ← delete_selected_records (4386)
- record_overlay        ← record_overlay_image    (4402)
- record_image          ← (yeni) orijinal form görüntüsü
- record_detail         ← record_detail           (4422)
- record_edit           ← record_edit_page        (4786)
- record_save           ← record_save_overrides   (5358)

Farklar:
- Her view giriş + sahiplik kontrolü yapar (kaynakta yoktu).
- Görüntüler base64 gömülmek yerine yetki kontrollü `record_image` /
  `record_overlay` URL'lerinden sunulur; dosya yolu batch klasörü dışındaysa
  (yol aşımı) sunulmaz.
- `return_url` yalnızca aynı siteye işaret ediyorsa kullanılır (açık yönlendirme
  koruması). "Kaydedildi" bilgisi query string yerine Django mesajıyla verilir.
"""
import json
import mimetypes
import os
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_GET, require_POST

from optik import store
from optik.permissions import get_batch_for_user, get_test_for_user
from optik.services import core as service
from optik.services import override as override_service
from optik.services.omr import detect_duplicate_students
from optik.wizard import wizard_context

ANSWER_CHOICES = ["A", "B", "C", "D", "E"]


# ── Ortak yardımcılar (scoring view'ları da kullanır) ───────────────────

def q_sort_key(item_id: str) -> int:
    """'Q12' → 12 (sayı değilse 0)."""
    s = str(item_id).replace("Q", "")
    return int(s) if s.isdigit() else 0


def safe_return_url(request, value: str) -> str:
    """Kullanıcıdan gelen return_url yalnızca bu siteye aitse döndürülür."""
    value = (value or "").strip()
    if value and url_has_allowed_host_and_scheme(
            value, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        return value
    return ""


def test_label(test: dict) -> str:
    return f"{test.get('course_code', '')} - {test.get('exam_type', '')}"


def base_context(test: dict, batch: dict = None) -> dict:
    """Breadcrumb ve başlıklar için ortak bağlam."""
    ctx = {
        'test': test,
        'test_id': test.get('test_id'),
        'course_code': test.get('course_code', ''),
        'test_label': test_label(test),
    }
    if batch:
        ctx['batch'] = batch
        ctx['batch_id'] = batch.get('batch_id')
    return ctx


def _answers_as_list(answers) -> list:
    if isinstance(answers, dict):
        return [answers[k] for k in sorted(answers, key=q_sort_key)]
    return list(answers or [])


def _display_count(test: dict, answers) -> int:
    """Gösterilecek soru sayısı: OMR yalnızca MCQ maddelerini okur."""
    question_counts = test.get("question_counts", {}) or {}
    mcq_count = question_counts.get("MCQ", 0) or 0
    num_items = mcq_count if mcq_count > 0 else (test.get("num_items", 0) or 0)
    if num_items:
        return num_items
    return len(answers) if isinstance(answers, (list, dict)) else 0


def _answer_values(answers, count: int) -> list:
    """Cevapları (liste veya {Qn: ..}) `count` uzunluğunda listeye çevir."""
    if isinstance(answers, list):
        return [(answers[i] or "") if i < len(answers) else "" for i in range(count)]
    if isinstance(answers, dict):
        return [answers.get(f"Q{i}", "") or "" for i in range(1, count + 1)]
    return [""] * count


def record_file_path(batch_id: str, record: dict, kind: str) -> str:
    """
    Kayda ait sunulabilir dosya yolu (yoksa "").

    kind="image": orijinal form (image_path, yoksa file_path)
    kind="overlay": overlay, yoksa orijinal forma düşer (kaynaktaki gibi)
    Yol batch klasörü dışındaysa kullanılmaz.
    """
    candidates = []
    if kind == "overlay":
        candidates.append(record.get("overlay_path", ""))
    candidates.append(record.get("image_path", "") or record.get("file_path", ""))
    for path in candidates:
        if path and store.is_inside_batch_dir(batch_id, path) and os.path.isfile(path):
            return path
    return ""


def _serve_file(path: str) -> FileResponse:
    mime = mimetypes.guess_type(path)[0] or "application/octet-stream"
    return FileResponse(open(path, "rb"), content_type=mime)


# ── Kayıt listesi ───────────────────────────────────────────────────────

def _effective_field(rec: dict, field: str):
    ov = rec.get("overrides", {}) or {}
    return ov.get(field, rec.get(field, ""))


def _is_missing(value) -> bool:
    return not value or value == "None"


def build_record_rows(records: list, defined_booklets: list, duplicates: list) -> dict:
    """
    Kayıt listesi tablosu: sıralama (hatalı → mükerrer → boş/çift → OK),
    satır uyarıları ve özet sayılar.
    """
    dup_student_nos = {d["student_no"] for d in duplicates}
    is_single_booklet = bool(defined_booklets) and len(defined_booklets) == 1

    def sort_key(rec):
        sno = _effective_field(rec, "student_no")
        bklt = _effective_field(rec, "booklet")
        has_err = (_is_missing(sno) or "?" in str(sno) or "!" in str(sno) or
                   _is_missing(bklt) or bklt in ("?", "!") or
                   bool(defined_booklets and bklt not in defined_booklets))
        has_dup = sno in dup_student_nos
        ans = _answers_as_list(rec.get("answers", []))
        has_temp = any(a == "" or a == "!" for a in ans)
        if has_err:
            priority = 0
        elif has_dup:
            priority = 1
        elif has_temp:
            priority = 2
        else:
            priority = 3
        # Aynı öncelik grubunda öğrenci numarasına göre sırala
        return (priority, str(sno or ""))

    rows = []
    warning_count = 0
    temp_warning_count = 0

    for idx, record in enumerate(sorted(records, key=sort_key), 1):
        student_no = _effective_field(record, "student_no")
        booklet = _effective_field(record, "booklet")
        is_dup = student_no in dup_student_nos

        warnings = []
        if _is_missing(student_no):
            warnings.append(("err", "Öğr. No Eksik"))
        elif "?" in str(student_no) or "!" in str(student_no):
            warnings.append(("err", "Öğr. No Hatalı"))

        # Tek kitapçık testinde kitapçık zaten sabit, uyarı verme
        if is_single_booklet:
            pass
        elif _is_missing(booklet):
            warnings.append(("err", "Kitapçık Eksik"))
        elif booklet in ("?", "!"):
            warnings.append(("err", "Kitapçık Hatalı"))
        elif defined_booklets and booklet not in defined_booklets:
            warnings.append(("err", "Geçersiz Kitapçık"))

        if is_dup:
            warnings.append(("dup", "Mükerrer"))

        # Cevap kontrolleri (geçici uyarılar)
        answers = _answers_as_list(record.get("answers", []))
        blank_count = sum(1 for a in answers if a == "")
        multi_count = sum(1 for a in answers if a == "!")
        if blank_count > 0:
            warnings.append(("temp", f"{blank_count} Boş"))
        if multi_count > 0:
            warnings.append(("temp", f"{multi_count} Çift"))

        has_err_or_dup = any(w[0] in ("err", "dup") for w in warnings)
        if has_err_or_dup:
            warning_count += 1
        elif warnings:
            temp_warning_count += 1

        rows.append({
            'idx': idx,
            'record_id': record.get("record_id", ""),
            'student_no': None if _is_missing(student_no) else student_no,
            'booklet': None if _is_missing(booklet) else booklet,
            'warnings': [{'type': t, 'text': txt} for t, txt in warnings],
            'row_class': 'optik-row-warn' if (has_err_or_dup or is_dup) else '',
        })

    total = len(records)
    return {
        'rows': rows,
        'total': total,
        'ok_count': total - warning_count - temp_warning_count,
        'warning_count': warning_count,
        'temp_warning_count': temp_warning_count,
        'dup_count': len(duplicates),
    }


@login_required
@require_GET
def test_records(request, test_id):
    """Kayıt Listesi - sihirbaz 4. adım."""
    get_test_for_user(request.user, test_id)
    test = service.get_test(test_id)
    batch_id = service.get_test_batch_id(test_id)

    ctx = base_context(test)
    ctx.update(wizard_context(test_id, 4))
    if not batch_id:
        ctx['no_batch'] = True
        return render(request, 'optik/records/list.html', ctx)

    records = service.get_batch_records(batch_id)
    duplicates = detect_duplicate_students(batch_id)
    ctx.update(build_record_rows(records, test.get("booklets", []) or [], duplicates))
    ctx.update({
        'batch_id': batch_id,
        'duplicates': [{'student_no': d['student_no'], 'count': d['count']} for d in duplicates],
    })
    return render(request, 'optik/records/list.html', ctx)


@login_required
@require_GET
def batch_detail(request, batch_id):
    """Batch sayfası → testin kayıt listesi (sihirbaz 4. adım)."""
    batch = get_batch_for_user(request.user, batch_id)
    return redirect('optik:records', test_id=batch.test.test_id)


@login_required
@require_POST
def record_delete(request, batch_id, record_id):
    """Tekli kayıt silme (JSON)."""
    get_batch_for_user(request.user, batch_id)
    if service.delete_record(batch_id, record_id):
        return JsonResponse({"success": True})
    return JsonResponse({"success": False, "error": "Kayıt bulunamadı"}, status=404)


@login_required
@require_POST
def delete_selected(request, batch_id):
    """Toplu kayıt silme. Gövde: {"record_ids": [...]} (JSON)."""
    get_batch_for_user(request.user, batch_id)
    try:
        body = json.loads(request.body or b"{}")
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({"success": False, "error": "Geçersiz istek"}, status=400)
    record_ids = body.get("record_ids", []) if isinstance(body, dict) else []
    if not isinstance(record_ids, list):
        return JsonResponse({"success": False, "error": "Geçersiz istek"}, status=400)
    record_ids = [str(r) for r in record_ids if r]
    if not record_ids:
        return JsonResponse({"success": False, "error": "Kayıt seçilmedi"}, status=400)

    deleted = service.delete_records(batch_id, record_ids)
    return JsonResponse({"success": True, "deleted": deleted})


# ── Görüntü sunumu ──────────────────────────────────────────────────────

def _get_record_or_404(batch_id: str, record_id: str) -> dict:
    try:
        return store.get_record(batch_id, record_id)
    except store.NotFound:
        raise Http404("Kayıt bulunamadı")


@login_required
@require_GET
def record_overlay(request, batch_id, record_id):
    """Overlay PNG; yoksa orijinal form görüntüsü."""
    get_batch_for_user(request.user, batch_id)
    record = _get_record_or_404(batch_id, record_id)
    path = record_file_path(batch_id, record, "overlay")
    if not path:
        return HttpResponse("Görüntü bulunamadı", status=404, content_type="text/plain; charset=utf-8")
    return _serve_file(path)


@login_required
@require_GET
def record_image(request, batch_id, record_id):
    """Orijinal (yüklenen) form görüntüsü."""
    get_batch_for_user(request.user, batch_id)
    record = _get_record_or_404(batch_id, record_id)
    path = record_file_path(batch_id, record, "image")
    if not path:
        return HttpResponse("Görüntü bulunamadı", status=404, content_type="text/plain; charset=utf-8")
    return _serve_file(path)


# ── Kayıt detay ─────────────────────────────────────────────────────────

def build_answer_cells(answer_values: list, key: dict, answers_overridden: bool) -> list:
    """Detay sayfası cevap ızgarası: öğrenci cevabı ile anahtar karşılaştırması."""
    cells = []
    for q_num, ans in enumerate(answer_values, 1):
        key_ans = key.get(f"Q{q_num}", "")
        if not ans:
            css = "optik-cell-blank"
        elif ans == "!":
            css = "optik-cell-multi"
        elif key_ans and key_ans != "?" and (key_ans == "*" or ans == key_ans):
            css = "optik-cell-correct"
        elif key_ans and key_ans != "?":
            css = "optik-cell-wrong"
        else:
            css = "optik-cell-filled"
        cells.append({'q': q_num, 'answer': ans or "-", 'key': key_ans,
                      'css': css, 'overridden': answers_overridden})
    return cells


@login_required
@require_GET
def record_detail(request, batch_id, record_id):
    """Kayıt detay sayfası (override'lar uygulanmış haliyle)."""
    batch_obj = get_batch_for_user(request.user, batch_id)
    return_url = safe_return_url(request, request.GET.get("return_url", ""))

    try:
        record_data = override_service.get_effective_result(batch_id, record_id)
    except store.NotFound:
        raise Http404("Kayıt bulunamadı")
    full_record = _get_record_or_404(batch_id, record_id)
    batch = service.get_batch(batch_id)
    test = service.get_test(batch_obj.test.test_id)

    effective = record_data["effective"]
    overrides = record_data["overrides"]
    has_overrides = record_data["has_overrides"]
    seating = effective.get("seating") or {}

    answers = effective.get("answers", {})
    count = _display_count(test, answers)
    values = _answer_values(answers, count) if (answers or count) else []
    key = (test.get("answer_keys", {}) or {}).get(effective.get("booklet", ""), {}) or {}
    cells = build_answer_cells(values, key, has_overrides and "answers" in overrides)

    total_questions = len(cells)
    total_answered = sum(1 for v in values if v)

    edit_url = reverse('optik:record_edit', args=[batch_id, record_id])
    if return_url:
        edit_url += "?" + urlencode({"return_url": return_url})

    ctx = base_context(test, batch)
    ctx.update({
        'record_id': record_id,
        'student_no': effective.get("student_no", ""),
        'class_code': effective.get("class_code", "") or "-",
        'booklet': effective.get("booklet", ""),
        'seating_id': seating.get("cell_id", "-") if isinstance(seating, dict) and seating else "-",
        'has_overrides': has_overrides,
        'override_fields': list(overrides.keys()),
        'cells': cells,
        'total_answered': total_answered,
        'total_blank': total_questions - total_answered,
        'completion': int((total_answered / total_questions * 100) if total_questions > 0 else 0),
        'has_image': bool(record_file_path(batch_id, full_record, "image")),
        'has_overlay': bool(full_record.get("overlay_path")
                            and store.is_inside_batch_dir(batch_id, full_record["overlay_path"])
                            and os.path.isfile(full_record["overlay_path"])),
        'return_url': return_url,
        'back_url': return_url or reverse('optik:records', args=[test["test_id"]]),
        'edit_url': edit_url,
    })
    return render(request, 'optik/records/detail.html', ctx)


# ── Kayıt düzenleme ─────────────────────────────────────────────────────

def build_edit_rows(values: list, raw_values: list, key: dict) -> list:
    """Düzenleme tablosu satırları: A–E / boş butonları, anahtar, OMR ham değeri."""
    rows = []
    for idx, ans in enumerate(values):
        q_num = idx + 1
        key_ans = key.get(f"Q{q_num}", "")
        raw_ans = raw_values[idx] if idx < len(raw_values) else ""
        options = [{'value': ch, 'label': ch, 'selected': ans == ch, 'correct': key_ans == ch}
                   for ch in ANSWER_CHOICES]
        options.append({'value': "", 'label': "-", 'selected': not ans, 'correct': False, 'empty': True})
        if key_ans and ans:
            status = "ok" if ans == key_ans else "wrong"
        else:
            status = ""
        rows.append({
            'q': q_num,
            'answer': ans,
            'key': key_ans,
            'options': options,
            'status': status,
            'raw': (raw_ans or "-") if raw_ans != ans else None,
            'changed': bool(raw_ans) and ans != raw_ans,
        })
    return rows


@login_required
@require_GET
def record_edit(request, batch_id, record_id):
    """Kayıt düzenleme sayfası - öğrenci no / sınıf / kitapçık + cevap butonları."""
    batch_obj = get_batch_for_user(request.user, batch_id)
    return_url = safe_return_url(request, request.GET.get("return_url", ""))

    try:
        result = override_service.get_effective_result(batch_id, record_id)
    except store.NotFound:
        raise Http404("Kayıt bulunamadı")
    full_record = _get_record_or_404(batch_id, record_id)
    batch = service.get_batch(batch_id)
    test = service.get_test(batch_obj.test.test_id)

    raw = result["raw"]
    effective = result["effective"]

    booklets = test.get("booklets", []) or []
    current_booklet = effective.get("booklet", "") or ""
    key = (test.get("answer_keys", {}) or {}).get(current_booklet, {}) or {}

    answers = effective.get("answers", [])
    raw_answers = raw.get("answers", [])
    count = _display_count(test, answers)
    values = _answer_values(answers, count)
    raw_values = _answer_values(raw_answers, count) if isinstance(raw_answers, type(answers)) \
        else [""] * count

    ctx = base_context(test, batch)
    ctx.update({
        'record_id': record_id,
        'student_no': effective.get("student_no", "") or "",
        'class_code': effective.get("class_code", "") or "",
        'raw_student_no': raw.get("student_no") or "-",
        'raw_class_code': raw.get("class_code") or "-",
        'raw_booklet': raw.get("booklet") or "-",
        'booklet_options': booklets or [current_booklet],
        'current_booklet': current_booklet,
        'rows': build_edit_rows(values, raw_values, key),
        'has_image': bool(record_file_path(batch_id, full_record, "image")),
        'return_url': return_url,
        'back_url': return_url or reverse('optik:records', args=[test["test_id"]]),
    })
    return render(request, 'optik/records/edit.html', ctx)


@login_required
@require_POST
def record_save(request, batch_id, record_id):
    """Kayıt düzenle - alanları doğrudan güncelle (+ overrides / override_history)."""
    get_batch_for_user(request.user, batch_id)
    record = _get_record_or_404(batch_id, record_id)
    post = request.POST

    student_no = post.get("student_no", "").strip()
    class_code = post.get("class_code", "").strip()
    booklet = post.get("booklet", "").strip()

    # Her zaman tüm alanları doğrudan güncelle (karşılaştırma yapmadan)
    record["student_no"] = student_no
    record["class_code"] = class_code
    record["booklet"] = booklet

    # Cevapları topla: ans_1, ans_2, ...
    ans_keys = sorted(
        [k for k in post.keys() if k.startswith("ans_") and k[4:].isdigit()],
        key=lambda k: int(k[4:])
    )
    if ans_keys:
        new_answers = [post.get(k, "").strip().upper() for k in ans_keys]
        old_answers = record.get("answers", [])
        # Cevapları mevcut formatla kaydet (list veya dict)
        if isinstance(old_answers, dict):
            record["answers"] = {f"Q{i + 1}": v for i, v in enumerate(new_answers)}
        else:
            record["answers"] = new_answers

    # Override bilgisini de güncelle (geriye uyumluluk)
    record.setdefault("overrides", {})
    if not isinstance(record["overrides"], dict):
        record["overrides"] = {}
    record["overrides"]["student_no"] = student_no
    record["overrides"]["class_code"] = class_code
    record["overrides"]["booklet"] = booklet

    record.setdefault("override_history", [])
    record["override_history"].append({
        "user_id": request.user.pk,
        "timestamp": store.now_iso(),
        "student_no": student_no,
        "class_code": class_code,
        "booklet": booklet,
    })

    record["updated_at"] = store.now_iso()
    service.save_record(batch_id, record_id, record)

    messages.success(request, "Kaydedildi")
    return_url = safe_return_url(request, post.get("return_url", ""))
    if return_url:
        return redirect(return_url)
    return redirect('optik:record_detail', batch_id=batch_id, record_id=record_id)
