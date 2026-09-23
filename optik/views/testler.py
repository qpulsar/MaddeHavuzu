"""
Optik ana sayfa + test oluşturma/düzenleme (sihirbaz 1. adım).

Kaynak: omr_analysis/routes.py
- GET  /omr/                          → index               (routes.py:49)
- GET  /omr/test/new                  → test_new            (routes.py:393)
- POST /omr/test/create               → test_create         (routes.py:796)
- GET  /omr/test/{id}                 → test_detail         (routes.py:1546)
- GET/POST /omr/test/{id}/edit        → test_edit           (routes.py:875/1031)
- POST /omr/test/{id}/remove-approval → test_remove_approval (routes.py:1079)

Farklar:
- Her view'da giriş + sahiplik kontrolü var (kaynakta yoktu).
- Sınav takvimi (exam_id/semester) bağlantısı yok: akademik yıl ve dönem
  serbest girilir; varsayılanları bugünün tarihinden hesaplanır.
- Doğrulama hataları düz HTML yerine formun hata listesiyle yeniden
  gösterilmesiyle (400) bildirilir.
"""
from datetime import date

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from optik.models import OptikTest
from optik.permissions import get_test_for_user, is_admin
from optik.services import core
from optik.wizard import STEPS, wizard_context

BOOKLET_CHOICES = ["A", "B", "C", "D"]
EXAM_TYPES = ["Vize", "Final", "Bütünleme", "Quiz"]
SEMESTERS = ["Güz", "Bahar", "Yaz"]
# Kaynaktaki sıralama: aynı yıl içinde Güz > Bahar > Yaz (ters sıralamayla)
SEMESTER_ORDER = {"Yaz": 0, "Bahar": 1, "Guz": 2, "Güz": 2}


# ── Yardımcılar ─────────────────────────────────────────────────────────

def current_academic_year(today: date = None) -> str:
    """Eylül ve sonrası yeni akademik yıl: 2026-09 → '2026-2027', 2026-03 → '2025-2026'."""
    today = today or date.today()
    start = today.year if today.month >= 9 else today.year - 1
    return f"{start}-{start + 1}"


def current_semester(today: date = None) -> str:
    """Ay'a göre dönem: Eylül–Ocak Güz, Şubat–Haziran Bahar, Temmuz–Ağustos Yaz."""
    today = today or date.today()
    if today.month >= 9 or today.month == 1:
        return "Güz"
    if 2 <= today.month <= 6:
        return "Bahar"
    return "Yaz"


def _academic_year_options(selected: str = "") -> list:
    start = int(current_academic_year()[:4])
    options = [f"{y}-{y + 1}" for y in range(start - 1, start + 2)]
    if selected and selected not in options:
        options.insert(0, selected)
    return options


def _with_current(options: list, selected: str) -> list:
    """Kayıtlı değer listede yoksa (ör. eski 'Guz', 'Butunleme') seçenek olarak ekle."""
    if selected and selected not in options:
        return options + [selected]
    return list(options)


def _static_steps(step: int) -> list:
    """Test henüz yokken (yeni test) gösterilecek bağlantısız stepper."""
    return [{'number': i, 'label': label, 'url': '#',
             'state': 'done' if i < step else ('active' if i == step else 'todo')}
            for i, (label, _) in enumerate(STEPS, start=1)]


def _parse_int(value, default=0):
    if value is None or str(value).strip() == "":
        return default
    return int(str(value).strip())


def parse_test_form(post) -> tuple:
    """
    Test oluşturma/düzenleme formunu oku ve doğrula.

    Returns: (values dict, errors list)
    """
    errors = []
    values = {
        'course_code': post.get('course_code', '').strip().upper(),
        'course_name': post.get('course_name', '').strip(),
        'exam_type': post.get('exam_type', '').strip(),
        'academic_year': post.get('academic_year', '').strip(),
        'semester': post.get('semester', '').strip(),
        'booklets': [b.strip().upper() for b in post.getlist('booklets') if b.strip()],
    }
    numbers = {}
    for field in ('mcq_count', 'open_count', 'mcq_points', 'open_points'):
        raw = post.get(field, '')
        try:
            numbers[field] = _parse_int(raw)
        except ValueError:
            numbers[field] = 0
            errors.append("Soru sayıları ve puanlar tam sayı olmalıdır.")
        values[field] = raw if raw is not None else ''
    errors = list(dict.fromkeys(errors))

    if not values['course_code']:
        errors.append("Ders kodu zorunludur.")
    if not values['course_name']:
        errors.append("Ders adı zorunludur.")
    if not values['exam_type']:
        errors.append("Sınav türü zorunludur.")

    invalid_booklets = [b for b in values['booklets'] if b not in BOOKLET_CHOICES]
    if invalid_booklets:
        errors.append("Geçersiz kitapçık: " + ", ".join(invalid_booklets))
    values['booklets'] = [b for b in dict.fromkeys(values['booklets']) if b in BOOKLET_CHOICES]
    if not values['booklets']:
        errors.append("En az bir kitapçık seçmelisiniz!")

    mcq_count, open_count = numbers['mcq_count'], numbers['open_count']
    mcq_points, open_points = numbers['mcq_points'], numbers['open_points']
    if min(mcq_count, open_count, mcq_points, open_points) < 0:
        errors.append("Soru sayıları ve puanlar negatif olamaz.")

    total_points = mcq_points + open_points
    if total_points != 100:
        errors.append(f"Toplam puan 100 olmalıdır! (Şu an: {total_points})")
    if mcq_count + open_count == 0:
        errors.append("En az bir soru girmelisiniz!")
    if mcq_count == 0 and mcq_points > 0:
        errors.append("Çoktan seçmeli madde sayısı 0 olduğu için puan girilemez!")
    if open_count == 0 and open_points > 0:
        errors.append("Açık uçlu madde sayısı 0 olduğu için puan girilemez!")
    if mcq_count > 0 and mcq_points == 0:
        errors.append("MCQ soru sayısı girdiniz ama puan 0. Lütfen MCQ puanını girin.")
    if open_count > 0 and open_points == 0:
        errors.append("Açık uçlu soru sayısı girdiniz ama puan 0. Lütfen OPEN puanını girin.")

    values['numbers'] = numbers
    return values, errors


def _form_context(values: dict) -> dict:
    """Test formu şablonu için seçenek listeleri."""
    return {
        'form': values,
        'academic_year_options': _academic_year_options(values.get('academic_year', '')),
        'semester_options': _with_current(SEMESTERS, values.get('semester', '')),
        'exam_type_options': _with_current(EXAM_TYPES, values.get('exam_type', '')),
        'booklet_choices': BOOKLET_CHOICES,
    }


# ── Ana sayfa ───────────────────────────────────────────────────────────

def _test_status(batch) -> dict:
    """Test kartı durum rozeti: hazırlanıyor / form yüklendi / puanlandı."""
    if batch is None:
        return {'key': 'pending', 'label': 'Hazırlanıyor', 'css': 'text-bg-secondary'}
    if batch.scores:
        return {'key': 'scored', 'label': 'Puanlandı', 'css': 'text-bg-warning'}
    return {'key': 'uploaded', 'label': 'Form Yüklendi', 'css': 'text-bg-primary'}


def build_test_card(test: OptikTest, show_creator: bool) -> dict:
    batches = list(test.batches.all())  # Meta.ordering: yeniden eskiye
    batch = batches[0] if batches else None
    status = _test_status(batch)
    data = test.data or {}
    created = data.get('created_at') or (test.created_at.isoformat() if test.created_at else '')
    return {
        'test_id': test.test_id,
        'course_code': test.course_code,
        'course_name': test.course_name,
        'exam_type': test.exam_type,
        'booklets': ", ".join(data.get('booklets', [])),
        'created_at': created[:10],
        'status': status,
        'batch_id': batch.batch_id if batch else None,
        'has_batch': batch is not None,
        'creator': core.user_display_name(test.owner) if show_creator else '',
    }


def group_test_cards(tests, show_creator: bool) -> list:
    """Testleri (akademik yıl, dönem) gruplarına ayır; en yeni yıl üstte, 'Diğer' en sonda."""
    groups = {}
    for test in tests:
        ay, sem = test.academic_year, test.semester
        key = (ay, sem) if ay and sem else ("", "Diğer")
        groups.setdefault(key, []).append(build_test_card(test, show_creator))

    def sort_key(item):
        ay, sem = item[0]
        if not ay:
            return ("", 99)
        return (ay, SEMESTER_ORDER.get(sem, 50))

    ordered = sorted(groups.items(), key=sort_key, reverse=True)
    normal = [g for g in ordered if g[0][0] != ""]
    other = [g for g in ordered if g[0][0] == ""]
    return [{'label': f"{ay} / {sem}" if ay else sem, 'tests': cards}
            for (ay, sem), cards in normal + other]


def instructor_options() -> list:
    """Test sahibi kullanıcılar (yönetici filtresi için), ada göre sıralı."""
    owner_ids = (OptikTest.objects.filter(deleted=False)
                 .values_list('owner_id', flat=True).distinct())
    users = get_user_model().objects.filter(pk__in=set(owner_ids))
    options = [(str(u.pk), core.user_display_name(u)) for u in users]
    options.sort(key=lambda x: x[1].lower())
    return options


@login_required
@require_GET
def index(request):
    admin = is_admin(request.user)
    qs = (OptikTest.objects.filter(deleted=False)
          .select_related('owner').prefetch_related('batches'))
    instructor_filter = ''
    options = []
    if admin:
        instructor_filter = request.GET.get('instructor', '').strip()
        options = instructor_options()
        if instructor_filter:
            qs = qs.filter(owner_id=instructor_filter) if instructor_filter.isdigit() else qs.none()
    else:
        qs = qs.filter(owner=request.user)

    tests = sorted(qs, key=lambda t: (t.data or {}).get('created_at', ''), reverse=True)
    groups = group_test_cards(tests, show_creator=admin and not instructor_filter)
    return render(request, 'optik/tests/index.html', {
        'groups': groups,
        'total_count': len(tests),
        'is_admin': admin,
        'instructor_filter': instructor_filter,
        'instructor_options': options,
    })


# ── Test oluşturma ──────────────────────────────────────────────────────

def _new_form_defaults(request) -> dict:
    prefill_code = request.GET.get('course_code', '').strip()
    values = {
        'course_code': prefill_code,
        'course_name': request.GET.get('course_name', '').strip() if prefill_code else '',
        'exam_type': request.GET.get('exam_type', '').strip() if prefill_code else '',
        'academic_year': current_academic_year(),
        'semester': current_semester(),
        'booklets': ['A'],
        'mcq_count': '20', 'open_count': '0', 'mcq_points': '100', 'open_points': '0',
    }
    return values, bool(prefill_code)


def _render_new(request, values, locked, errors=None, status=200):
    ctx = _form_context(values)
    ctx.update({'prefill_locked': locked, 'errors': errors or [],
                'wizard_steps_static': _static_steps(1)})
    return render(request, 'optik/tests/new.html', ctx, status=status)


@login_required
@require_GET
def test_new(request):
    values, locked = _new_form_defaults(request)
    return _render_new(request, values, locked)


@login_required
@require_POST
def test_create(request):
    values, errors = parse_test_form(request.POST)
    locked = request.POST.get('prefill_locked') == '1'
    if errors:
        return _render_new(request, values, locked, errors, status=400)

    n = values['numbers']
    test_id = core.create_test(
        values['course_code'], values['course_name'], values['exam_type'],
        values['booklets'], n['mcq_count'] + n['open_count'], request.user,
        question_types={"MCQ": n['mcq_count'], "TF": 0, "OPEN": n['open_count']},
        points_by_type={"MCQ": float(n['mcq_points']), "TF": 0.0, "OPEN": float(n['open_points'])},
        academic_year=values['academic_year'] or None,
        semester=values['semester'] or None,
    )
    messages.success(request, "Test oluşturuldu.")
    return redirect('optik:upload_forms', test_id=test_id)


@login_required
@require_GET
def test_detail(request, test_id):
    get_test_for_user(request.user, test_id)
    return redirect('optik:test_edit', test_id=test_id)


# ── Test düzenleme ──────────────────────────────────────────────────────

def _edit_values(test: dict) -> dict:
    qc = test.get("question_counts", {})
    pts = test.get("points_by_type_total", {})
    return {
        'course_code': test.get('course_code', ''),
        'course_name': test.get('course_name', ''),
        'exam_type': test.get('exam_type', ''),
        'academic_year': test.get('academic_year', ''),
        'semester': test.get('semester', ''),
        'booklets': test.get('booklets', []),
        'mcq_count': str(qc.get("MCQ", 0)),
        'open_count': str(qc.get("OPEN", 0)),
        'mcq_points': str(int(pts.get("MCQ", 100))),
        'open_points': str(int(pts.get("OPEN", 0))),
    }


def _render_edit(request, test_id, test, values, errors=None, status=200):
    ctx = _form_context(values)
    ctx.update(wizard_context(test_id, 1))
    ctx.update({'test_id': test_id, 'test': test, 'errors': errors or [],
                'is_approved': bool(test.get('is_approved'))})
    return render(request, 'optik/tests/edit.html', ctx, status=status)


@login_required
@require_http_methods(["GET", "POST"])
def test_edit(request, test_id):
    get_test_for_user(request.user, test_id)
    test = core.get_test(test_id)

    if request.method == "GET":
        return _render_edit(request, test_id, test, _edit_values(test))

    if test.get("is_approved", False):
        raise PermissionDenied("Onaylı test düzenlenemez. Önce onayı kaldırın.")

    values, errors = parse_test_form(request.POST)
    if errors:
        return _render_edit(request, test_id, test, values, errors, status=400)

    n = values['numbers']
    update_data = {
        "course_code": values['course_code'],
        "course_name": values['course_name'],
        "exam_type": values['exam_type'],
        "booklets": values['booklets'],
        "num_items": n['mcq_count'] + n['open_count'],
        "question_counts": {"MCQ": n['mcq_count'], "TF": 0, "OPEN": n['open_count']},
        "points_by_type_total": {"MCQ": float(n['mcq_points']), "TF": 0.0,
                                 "OPEN": float(n['open_points'])},
    }
    if values['academic_year']:
        update_data["academic_year"] = values['academic_year']
    if values['semester']:
        update_data["semester"] = values['semester']
    core.update_test(test_id, update_data)
    core.auto_set_item_points(test_id)
    messages.success(request, "Test bilgileri kaydedildi.")
    return redirect('optik:upload_forms', test_id=test_id)


@login_required
@require_POST
def test_remove_approval(request, test_id):
    get_test_for_user(request.user, test_id)
    core.set_test_approval(test_id, False)
    messages.success(request, "Test onayı kaldırıldı.")
    return redirect('optik:test_detail', test_id=test_id)
