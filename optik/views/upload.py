"""
Form yükleme (sihirbaz 2. adım) ve işleme ilerlemesi.

Kaynak: omr_analysis/routes.py
- GET/POST /omr/test/{id}/upload-forms   → upload_forms  (routes.py:1090/1328)
- GET      /omr/batch/{id}/progress      → progress      (routes.py:4126)
- GET      /omr/batch/{id}/progress-api  → progress_api  (routes.py:4349)

Farklar:
- Sınav son yükleme tarihi kontrolü yok (bu projede sınav takvimi yok).
- Yalnızca .jpg/.jpeg/.png kabul edilir; dosya adları uuid önekli ve
  temizlenmiş olarak batch'in uploads klasörüne yazılır.
- OMR işleme `background.start_processing` ile iş parçacığı havuzunda yapılır.
- Hatalar düz HTML yerine mesajla forma geri yönlendirilerek bildirilir.
- Kaynaktaki TXT yükleme (routes.py:1412, yalnızca yönetici) kaldırıldı;
  formlar yalnızca görüntüden okunur.
"""
import os
import uuid

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.text import get_valid_filename
from django.views.decorators.http import require_GET, require_http_methods

from optik import store
from optik.permissions import get_batch_for_user, get_test_for_user
from optik.services import background
from optik.services import core
from optik.wizard import wizard_context

ALLOWED_IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png'}
ANSWER_KEY_STUDENT_NO = "111111111111"


# ── Yardımcılar ─────────────────────────────────────────────────────────

def safe_upload_name(filename: str) -> str:
    """uuid önekli, yol bileşeni içermeyen, temizlenmiş dosya adı."""
    base = os.path.basename((filename or '').replace('\\', '/'))
    try:
        cleaned = get_valid_filename(base)
    except Exception:  # Django: boş/geçersiz ad → SuspiciousFileOperation
        cleaned = 'form' + os.path.splitext(base)[1].lower()
    return f"{uuid.uuid4().hex[:8]}_{cleaned[:120]}"


def save_uploaded_images(batch_id: str, files) -> tuple:
    """
    Yüklenen görüntüleri batch uploads klasörüne kaydet.

    Returns: (kaydedilen yollar, reddedilen dosya adları)
    """
    upload_dir = store.get_upload_dir(batch_id)
    saved, rejected = [], []
    for f in files:
        ext = os.path.splitext(f.name or '')[1].lower()
        if ext not in ALLOWED_IMAGE_EXTENSIONS:
            rejected.append(f.name)
            continue
        if not f.size:
            continue
        path = os.path.join(upload_dir, safe_upload_name(f.name))
        with open(path, 'wb') as out:
            for chunk in f.chunks():
                out.write(chunk)
        saved.append(path)
    return saved, rejected


def default_batch_name(test: dict) -> str:
    """Batch adı: Akademik Yıl/Ders Kodu/Sınav Türü."""
    return f"{test.get('academic_year') or '-'}/{test.get('course_code', '')}/{test.get('exam_type', '')}"


def _ensure_not_approved(test: dict) -> None:
    if test.get("is_approved", False):
        raise PermissionDenied("Onaylı teste form eklenemez. Önce onayı kaldırın.")


# ── Form yükleme ────────────────────────────────────────────────────────

@login_required
@require_http_methods(["GET", "POST"])
def upload_forms(request, test_id):
    get_test_for_user(request.user, test_id)
    test = core.get_test(test_id)

    if request.method == "POST":
        return _upload_forms_post(request, test_id, test)

    ctx = wizard_context(test_id, 2)
    batch_id = core.get_test_batch_id(test_id)
    ctx.update({
        'test_id': test_id,
        'test': test,
        'is_approved': bool(test.get('is_approved')),
        'existing_batch': batch_id is not None,
        'record_count': core.get_record_count(batch_id) if batch_id else 0,
        'batch_name': default_batch_name(test),
        'answer_key_student_no': ANSWER_KEY_STUDENT_NO,
    })
    return render(request, 'optik/upload/forms.html', ctx,
                  status=403 if ctx['is_approved'] else 200)


def _upload_forms_post(request, test_id, test):
    _ensure_not_approved(test)
    files = request.FILES.getlist('files')
    if not files:
        messages.error(request, "Dosya seçilmedi.", extra_tags='danger')
        return redirect('optik:upload_forms', test_id=test_id)

    batch_id = core.get_test_batch_id(test_id)
    if not batch_id:
        batch_name = request.POST.get('batch_name', '').strip()[:200] or default_batch_name(test)
        batch_id = core.create_batch(test_id, batch_name, request.user)

    image_paths, rejected = save_uploaded_images(batch_id, files)
    if rejected:
        messages.warning(request, "Desteklenmeyen dosyalar atlandı (yalnızca JPG/PNG): "
                         + ", ".join(rejected[:10]) + (" ..." if len(rejected) > 10 else ""))
    if not image_paths:
        messages.error(request, "Geçerli dosya yok.", extra_tags='danger')
        return redirect('optik:upload_forms', test_id=test_id)

    background.start_processing(batch_id, image_paths, user=request.user)
    return redirect('optik:progress', batch_id=batch_id)


# ── İlerleme ────────────────────────────────────────────────────────────

@login_required
@require_GET
def progress(request, batch_id):
    batch = get_batch_for_user(request.user, batch_id)
    test_id = batch.test.test_id
    return render(request, 'optik/upload/progress.html', {
        'batch_id': batch_id,
        'test_id': test_id,
        'test': batch.test,
        'next_url': reverse('optik:answer_key', args=[test_id]),
        'retry_url': reverse('optik:upload_forms', args=[test_id]),
        'api_url': reverse('optik:progress_api', args=[batch_id]),
    })


@login_required
@require_GET
def progress_api(request, batch_id):
    get_batch_for_user(request.user, batch_id)
    try:
        return JsonResponse(background.get_batch_progress(batch_id))
    except store.NotFound as e:
        return JsonResponse({"error": str(e)}, status=404)
