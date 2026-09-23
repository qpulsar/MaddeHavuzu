"""
Cevap anahtarı, kitapçık eşleştirmesi ve madde puanları (sihirbaz 3. adım).

Kaynak: omr_analysis/routes.py
- GET  /omr/test/{id}/answer-key            → answer_key            (routes.py:1553)
- POST /omr/test/{id}/save-answer-key       → save_answer_key       (routes.py:2359)
- POST /omr/test/{id}/save-all-answer-keys  → save_all_answer_keys  (routes.py:2398)
- POST /omr/test/{id}/auto-save-answer-keys → auto_save_answer_keys (routes.py:2435, JSON)
- POST /omr/test/{id}/save-item-points      → save_item_points      (routes.py:2460)
- POST /omr/test/{id}/save-detailed-points  → save_detailed_points  (routes.py:2487)
- POST /omr/test/{id}/save-booklet-mapping  → save_booklet_mapping  (routes.py:2515)
- GET/POST /omr/test/{id}/answer-key/upload → answer_key_upload     (routes.py:2552/2647)

Farklar:
- ?success= yerine Django messages kullanılır (?tab= korunur; eski ?success=
  bağlantıları da gösterilir).
- Cevap değerleri A–E ve * ile, madde kimlikleri Q1..Qn ile, kitapçıklar testin
  kitapçıklarıyla, eşleştirme değerleri 1..n aralığıyla sınırlandırıldı.
- Geçersiz sayı girişi 500 yerine hata mesajıyla sayfaya dönülür.
"""
import json
import os
import zipfile

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from optik.permissions import get_test_for_user
from optik.services import core
from optik.wizard import wizard_context

ANSWER_OPTIONS = ["A", "B", "C", "D", "E"]
VALID_ANSWERS = set(ANSWER_OPTIONS) | {"*"}
TABS = ("items", "answers", "points")


# ── Yardımcılar ─────────────────────────────────────────────────────────

def _answer_key_url(test_id: str, tab: str = None) -> str:
    url = reverse('optik:answer_key', args=[test_id])
    return f"{url}?tab={tab}" if tab else url


def _num_items(test: dict) -> int:
    try:
        return int(test.get("num_items", 50))
    except (TypeError, ValueError):
        return 0


def _collect_answers(data, booklet: str, num_items: int) -> dict:
    """Form/JSON'dan `answer_<kitapçık>_Q<n>` alanlarını topla (yalnızca dolu ve geçerli olanlar)."""
    answers = {}
    for i in range(1, num_items + 1):
        item_id = f"Q{i}"
        value = data.get(f"answer_{booklet}_{item_id}", "")
        value = str(value or "").strip().upper()
        if value in VALID_ANSWERS:
            answers[item_id] = value
    return answers


def _fmt_points(value) -> str:
    """Puanı input değeri olarak yaz (5.0 → '5.0', 3.3333 → '3.33')."""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return "0"
    return repr(round(v, 4)) if v != int(v) else f"{v:.1f}"


def build_answer_key_context(test: dict) -> dict:
    """Sayfanın tüm tablo satırlarını hazırla (şablonda hesaplama yapılmaz)."""
    booklets = test.get("booklets", [])
    num_items = _num_items(test)
    answer_keys = test.get("answer_keys", {})
    items = test.get("items", {})
    booklet_mapping = test.get("booklet_mapping", {})

    qc = test.get("question_counts", {})
    pts = test.get("points_by_type_total", {})
    mcq_count = qc.get("MCQ", num_items)
    open_count = qc.get("OPEN", 0)
    mcq_points_total = pts.get("MCQ", 100.0)
    open_points_total = pts.get("OPEN", 0.0)
    default_mcq = round(mcq_points_total / mcq_count, 2) if mcq_count > 0 else 0
    default_open = round(open_points_total / open_count, 2) if open_count > 0 else 0

    other_booklets = [b for b in booklets if b != "A"]
    show_mapping = len(booklets) > 1 and "A" in booklets
    item_numbers = list(range(1, num_items + 1))

    mapping_rows = []
    if show_mapping:
        for i in item_numbers:
            item_id = f"Q{i}"
            cells = []
            for b in other_booklets:
                try:
                    current = int(booklet_mapping.get(b, {}).get(item_id, i))
                except (TypeError, ValueError):
                    current = i
                cells.append({'name': f"mapping_{b}_{item_id}", 'value': current, 'booklet': b})
            mapping_rows.append({'number': i, 'cells': cells})

    answer_choices = [("", "-")] + [(o, o) for o in ANSWER_OPTIONS] + [("*", "* (Hatalı - Herkese Tam Puan)")]
    answer_rows = []
    for i in item_numbers:
        item_id = f"Q{i}"
        is_open = i > mcq_count
        cells = []
        for b in booklets:
            cells.append({
                'name': f"answer_{b}_{item_id}",
                'value': answer_keys.get(b, {}).get(item_id, ""),
                'booklet': b,
            })
        answer_rows.append({'number': i, 'item_id': item_id, 'is_open': is_open, 'cells': cells})

    def points_rows(start, end, default):
        return [{'number': i, 'name': f"points_Q{i}",
                 'value': _fmt_points(items.get(f"Q{i}", {}).get("points", default))}
                for i in range(start, end + 1)]

    return {
        'booklets': booklets,
        'other_booklets': other_booklets,
        'num_items': num_items,
        'mcq_count': mcq_count,
        'open_count': open_count,
        'mcq_points_total': mcq_points_total,
        'open_points_total': open_points_total,
        'default_mcq_points': default_mcq,
        'default_open_points': default_open,
        'show_mapping': show_mapping,
        'item_numbers': item_numbers,
        'mapping_rows': mapping_rows,
        'answer_choices': answer_choices,
        'answer_rows': answer_rows,
        'mcq_points_rows': points_rows(1, mcq_count, default_mcq),
        'open_points_rows': points_rows(mcq_count + 1, num_items, default_open),
        'open_start': mcq_count + 1,
    }


# ── Sayfa ───────────────────────────────────────────────────────────────

@login_required
@require_GET
def answer_key(request, test_id):
    get_test_for_user(request.user, test_id)
    test = core.get_test(test_id)
    tab = request.GET.get("tab", "answers")
    ctx = wizard_context(test_id, 3)
    ctx.update(build_answer_key_context(test))
    ctx.update({
        'test_id': test_id,
        'test': test,
        'active_tab': tab if tab in TABS else "answers",
        'success': request.GET.get('success', ''),
    })
    return render(request, 'optik/answer_key/answer_key.html', ctx)


# ── Kaydetme işlemleri ─────────────────────────────────────────────────

@login_required
@require_POST
def save_answer_key(request, test_id):
    get_test_for_user(request.user, test_id)
    test = core.get_test(test_id)
    save_booklet = request.POST.get("save_booklet", "").strip().upper()
    if not save_booklet:
        messages.error(request, "Kitapçık seçilmedi.", extra_tags='danger')
        return redirect(_answer_key_url(test_id))
    if save_booklet not in test.get("booklets", []):
        messages.error(request, f"Geçersiz kitapçık: {save_booklet}", extra_tags='danger')
        return redirect(_answer_key_url(test_id))

    answers = _collect_answers(request.POST, save_booklet, _num_items(test))
    core.set_answer_key(test_id, save_booklet, answers)
    core.auto_set_item_points(test_id)
    messages.success(request, f"Kitapçık {save_booklet} kaydedildi!")
    return redirect(_answer_key_url(test_id))


@login_required
@require_POST
def save_all_answer_keys(request, test_id):
    get_test_for_user(request.user, test_id)
    test = core.get_test(test_id)
    num_items = _num_items(test)
    saved_count = 0
    for booklet in test.get("booklets", []):
        answers = _collect_answers(request.POST, booklet, num_items)
        if answers:
            core.set_answer_key(test_id, booklet, answers)
            saved_count += 1
    core.auto_set_item_points(test_id)
    messages.success(request, f"{saved_count} kitapçık kaydedildi!")
    return redirect(_answer_key_url(test_id))


@login_required
@require_POST
def auto_save_answer_keys(request, test_id):
    get_test_for_user(request.user, test_id)
    try:
        body = json.loads(request.body or b"{}")
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({"ok": False, "error": "Geçersiz JSON"}, status=400)
    if not isinstance(body, dict):
        return JsonResponse({"ok": False, "error": "Geçersiz veri"}, status=400)

    test = core.get_test(test_id)
    num_items = _num_items(test)
    saved = []
    for booklet in test.get("booklets", []):
        answers = _collect_answers(body, booklet, num_items)
        if answers:
            core.set_answer_key(test_id, booklet, answers)
            saved.append(booklet)
    return JsonResponse({"ok": True, "saved_booklets": saved})


@login_required
@require_POST
def save_item_points(request, test_id):
    get_test_for_user(request.user, test_id)
    test = core.get_test(test_id)
    try:
        equal_points = float(request.POST.get("equal_points", 0) or 0)
    except ValueError:
        messages.error(request, "Geçersiz puan değeri.", extra_tags='danger')
        return redirect(_answer_key_url(test_id, "points"))
    if equal_points < 0:
        messages.error(request, "Puan negatif olamaz.", extra_tags='danger')
        return redirect(_answer_key_url(test_id, "points"))
    core.set_item_points(test_id, {f"Q{i}": equal_points for i in range(1, _num_items(test) + 1)})
    messages.success(request, "Puanlar kaydedildi!")
    return redirect(_answer_key_url(test_id))


@login_required
@require_POST
def save_detailed_points(request, test_id):
    get_test_for_user(request.user, test_id)
    test = core.get_test(test_id)
    points = {}
    for i in range(1, _num_items(test) + 1):
        item_id = f"Q{i}"
        raw = request.POST.get(f"points_{item_id}", "")
        try:
            value = float(raw) if str(raw).strip() else 0.0
        except ValueError:
            messages.error(request, f"Madde {i} için geçersiz puan: {raw}", extra_tags='danger')
            return redirect(_answer_key_url(test_id, "points"))
        if value < 0:
            messages.error(request, f"Madde {i} puanı negatif olamaz.", extra_tags='danger')
            return redirect(_answer_key_url(test_id, "points"))
        points[item_id] = value
    core.set_item_points(test_id, points)
    messages.success(request, "Puanlar kaydedildi!")
    return redirect(_answer_key_url(test_id, "points"))


@login_required
@require_POST
def save_booklet_mapping(request, test_id):
    get_test_for_user(request.user, test_id)
    test = core.get_test(test_id)
    num_items = _num_items(test)
    mapping = {}
    for booklet in test.get("booklets", []):
        if booklet == "A":
            continue  # A referans kitapçık
        mapping[booklet] = {}
        for i in range(1, num_items + 1):
            item_id = f"Q{i}"
            raw = request.POST.get(f"mapping_{booklet}_{item_id}", i)
            try:
                mapped = int(raw)
            except (TypeError, ValueError):
                mapped = 0
            if not 1 <= mapped <= num_items:
                messages.error(request, f"{booklet} kitapçığı madde {i} için geçersiz eşleştirme.",
                               extra_tags='danger')
                return redirect(_answer_key_url(test_id))
            mapping[booklet][item_id] = mapped
    core.set_booklet_mapping(test_id, mapping)
    messages.success(request, "Eşleştirme kaydedildi!")
    return redirect(_answer_key_url(test_id))


# ── Excel ile yükleme ──────────────────────────────────────────────────

@login_required
@require_http_methods(["GET", "POST"])
def answer_key_upload(request, test_id):
    get_test_for_user(request.user, test_id)
    test = core.get_test(test_id)
    ctx = {'test_id': test_id, 'test': test,
           'booklets': ", ".join(test.get("booklets", ["A"])), 'error': None}

    if request.method == "GET":
        return render(request, 'optik/answer_key/upload.html', ctx)

    upload = request.FILES.get("file")
    if not upload:
        ctx['error'] = "Dosya seçilmedi."
        return render(request, 'optik/answer_key/upload.html', ctx, status=400)
    if os.path.splitext(upload.name)[1].lower() != ".xlsx":
        ctx['error'] = "Yalnızca .xlsx formatındaki Excel dosyaları yüklenebilir."
        return render(request, 'optik/answer_key/upload.html', ctx, status=400)

    try:
        core.import_answer_keys_from_excel(test_id, upload.read())
    except ValueError as e:
        ctx['error'] = str(e)
        return render(request, 'optik/answer_key/upload.html', ctx, status=400)
    except (zipfile.BadZipFile, KeyError, OSError) as e:
        ctx['error'] = f"Excel dosyası okunamadı: {e}"
        return render(request, 'optik/answer_key/upload.html', ctx, status=400)

    messages.success(request, "Cevap anahtarı Excel'den yüklendi!")
    return redirect(_answer_key_url(test_id))
