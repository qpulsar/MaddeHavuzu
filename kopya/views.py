"""
Kopya Analizi view'ları (kaynak: cheating/routes.py).

  GET  /kopya/                         → sınav listesi (optik batch + Excel yüklemeleri)
  GET  /kopya/upload/                  → Excel yükleme formu
  POST /kopya/upload/                  → doğrulama + önizleme (dosya staging'e)
  POST /kopya/upload/analyze/          → KopyaUpload oluştur + analizi başlat
  GET  /kopya/template.xlsx            → boş şablon
  GET  /kopya/<source_id>/             → panel
  GET  /kopya/<source_id>/pair/<c>/<s>/ → çift detayı

Yetki: giriş zorunlu. Optik batch'ler test sahibine veya yöneticiye; Excel
yüklemeleri yükleyene veya yöneticiye açıktır (kaynakta sahiplik kontrolü
yalnızca listelemede vardı).
"""
from __future__ import annotations

import logging
import os
import time
import uuid
from datetime import datetime, timezone
from urllib.parse import urlencode

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.files.base import ContentFile
from django.http import Http404, HttpResponse
from django.shortcuts import redirect, render
from django.urls import NoReverseMatch, reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods, require_POST

from kopya import presenters, runner
from kopya.models import KopyaUpload
from optik.models import OptikTest
from optik.permissions import get_batch_for_user, is_admin

logger = logging.getLogger(__name__)

MAX_UPLOAD_BYTES = 20 * 1024 * 1024  # 20 MB
STAGING_TTL_HOURS = 24
SESSION_UID = "kopya_upload_uid"
SESSION_NAME = "kopya_upload_name"


# ── Yardımcılar ───────────────────────────────────────────────────────────

def _error(request, message: str, status: int = 200, back_url: str | None = None,
           back_label: str = "Kopya Analizi listesine dön"):
    return render(request, "kopya/error.html", {
        "message": message,
        "back_url": back_url or reverse("kopya:index"),
        "back_label": back_label,
    }, status=status)


def _check_source_access(user, source_id: str) -> None:
    """Kaynağa erişim: yoksa Http404, yetkisizse PermissionDenied."""
    if runner.is_excel_source(source_id):
        upload = KopyaUpload.objects.filter(upload_id=source_id).first()
        if upload is None:
            raise Http404("Excel yüklemesi bulunamadı")
        if upload.owner_id != user.id and not is_admin(user):
            raise PermissionDenied("Bu yüklemeye erişim yetkiniz yok.")
        return
    get_batch_for_user(user, source_id)


def _uploader_display(user) -> str:
    return user.get_full_name() or user.get_username() or str(user.pk)


def _batch_size(batch) -> int:
    data = batch.data or {}
    for k in ("record_count", "n_records"):
        try:
            v = int(data.get(k) or 0)
        except (TypeError, ValueError):
            v = 0
        if v:
            return v
    if batch.scores:
        return len(batch.scores.get("records", []) or [])
    return 0


def _computing(request, source_id: str, elapsed_s: float, hint: str):
    resp = render(request, "kopya/computing.html", {
        "source_id": source_id,
        "elapsed": f"{elapsed_s:.0f}",
        "hint": hint,
    })
    resp["Refresh"] = "3"
    resp["Cache-Control"] = "no-store"
    return resp


# ── Staging (Excel önizleme ile onay arasındaki geçici dosya) ─────────────

def staging_dir() -> str:
    return os.path.join(str(settings.MEDIA_ROOT), "kopya", "staging")


def _staging_path(uid: str) -> str:
    return os.path.join(staging_dir(), f"{uid}.xlsx")


def cleanup_old_staging(stage_dir: str, ttl_hours: int = STAGING_TTL_HOURS) -> None:
    """24 saatten eski staging dosyalarını sil."""
    now = time.time()
    ttl_s = ttl_hours * 3600
    try:
        names = os.listdir(stage_dir)
    except FileNotFoundError:
        return
    for fn in names:
        if not fn.endswith(".xlsx"):
            continue
        p = os.path.join(stage_dir, fn)
        try:
            if now - os.path.getmtime(p) > ttl_s:
                os.unlink(p)
        except OSError:
            pass


def _valid_uid(uid: str) -> bool:
    return bool(uid) and len(uid) == 16 and all(c in "0123456789abcdef" for c in uid)


# ── Liste ─────────────────────────────────────────────────────────────────

@login_required
@never_cache
def index(request):
    user = request.user
    admin = is_admin(user)

    tests = OptikTest.objects.filter(deleted=False).prefetch_related("batches")
    if not admin:
        tests = tests.filter(owner=user)
    tests = tests.select_related("owner").order_by("-created_at")

    grouped: dict = {}
    all_batch_ids = []
    for test in tests:
        batches = sorted(test.batches.all(), key=lambda b: b.created_at, reverse=True)
        if not batches:
            continue
        term = presenters.term_label(test.academic_year, test.semester)
        grouped.setdefault(term, []).append((test, batches))
        all_batch_ids.extend(b.batch_id for b in batches)

    uploads = KopyaUpload.objects.select_related("owner")
    if not admin:
        uploads = uploads.filter(owner=user)
    uploads = list(uploads.order_by("-created_at"))

    states = runner.analysis_states(all_batch_ids + [u.upload_id for u in uploads])

    groups = []
    n_shown = 0
    for term in sorted(grouped.keys(), key=presenters.term_sort_key):
        rows = []
        for test, batches in grouped[term]:  # test'ler zaten yeniden eskiye
            for batch in batches:
                scored = bool(batch.scores and (batch.scores.get("records") or []))
                rows.append({
                    "batch_id": batch.batch_id,
                    "course_code": test.course_code,
                    "course_name": test.course_name,
                    "exam_type": test.exam_type,
                    "name": (batch.data or {}).get("batch_name") or (batch.data or {}).get("name") or batch.batch_id,
                    "n_students": _batch_size(batch),
                    "date": batch.created_at.strftime("%Y-%m-%d") if batch.created_at else "",
                    "scored": scored,
                    "state": states.get(batch.batch_id, "none") if scored else "unscored",
                    "owner": test.owner.get_username() if admin else "",
                })
        n_shown += len(rows)
        groups.append({"term": term, "rows": rows,
                       "n_unscored": sum(1 for r in rows if not r["scored"])})

    upload_rows = []
    for u in uploads:
        m = u.meta or {}
        upload_rows.append({
            "upload_id": u.upload_id,
            "fname": m.get("fname") or u.original_filename,
            "uploader": m.get("uploaded_by_display") or u.owner.get_username(),
            "date": presenters.short_date(m.get("uploaded_at") or u.created_at.isoformat()),
            "n_students": int(m.get("n_students") or m.get("n_records") or 0),
            "state": states.get(u.upload_id, "none"),
        })

    return render(request, "kopya/index.html", {
        "groups": groups,
        "n_shown": n_shown,
        "uploads": upload_rows,
        "is_admin": admin,
    })


# ── Excel yükleme ─────────────────────────────────────────────────────────

@login_required
@never_cache
@require_http_methods(["GET", "POST"])
def upload(request):
    if request.method == "GET":
        return render(request, "kopya/upload.html", {"max_mb": MAX_UPLOAD_BYTES // (1024 * 1024)})

    f = request.FILES.get("file")
    if f is None:
        return _error(request, "Dosya seçilmedi.", status=400,
                      back_url=reverse("kopya:excel_upload"), back_label="Tekrar dene")
    if f.size > MAX_UPLOAD_BYTES:
        return _error(request, "Dosya 20 MB üstünde; parçalayıp yükleyin.", status=400,
                      back_url=reverse("kopya:excel_upload"), back_label="Tekrar dene")
    contents = f.read()
    filename = os.path.basename(f.name or "") or "sinav.xlsx"

    from kopya.engine.excel_upload import read_excel
    r = read_excel(contents)
    v = r.validation

    uid = None
    if v.ok:
        # Disk tabanlı staging: dosya MEDIA_ROOT/kopya/staging/<uid>.xlsx,
        # oturumda yalnız uid + dosya adı. KopyaUpload onayda oluşturulur.
        uid = uuid.uuid4().hex[:16]
        stage_dir = staging_dir()
        os.makedirs(stage_dir, exist_ok=True)
        cleanup_old_staging(stage_dir)
        with open(_staging_path(uid), "wb") as out:
            out.write(contents)
        request.session[SESSION_UID] = uid
        request.session[SESSION_NAME] = filename

    n = v.n_students
    return render(request, "kopya/upload_preview.html", {
        "v": v,
        "uid": uid,
        "filename": filename,
        "seat_coverage_pct": f"{v.seat_coverage * 100:.0f}",
        "n_directed": n * (n - 1) if n else 0,
        "n_minus_1": max(n - 1, 0),
    })


@login_required
@require_POST
def upload_analyze(request):
    from kopya.engine.excel_upload import read_excel

    uid = (request.POST.get("uid") or "").strip()
    sess_uid = request.session.get(SESSION_UID)
    fname = request.session.get(SESSION_NAME, "sinav.xlsx")
    retry = {"back_url": reverse("kopya:excel_upload"), "back_label": "Dosyayı yeniden yükle"}
    if not sess_uid or sess_uid != uid or not _valid_uid(uid):
        return _error(request, "Yükleme oturumu eşleşmedi. Lütfen dosyayı yeniden yükleyin.",
                      status=400, **retry)
    stage_path = _staging_path(uid)
    if not os.path.exists(stage_path):
        return _error(request, "Geçici dosya bulunamadı (süresi dolmuş olabilir). "
                               "Lütfen dosyayı yeniden yükleyin.", status=400, **retry)
    with open(stage_path, "rb") as fh:
        contents = fh.read()
    r = read_excel(contents)
    if not r.validation.ok:
        return _error(request, "; ".join(r.validation.blocking_errors), status=400, **retry)

    data = r.exam_data
    upload_id = "xl_" + uid
    n_booklets = int(data.booklet.max()) + 1
    n_records = int(data.responses.shape[0])
    n_items = int(data.responses.shape[1])
    user = request.user
    meta = {
        "batch_id": upload_id,
        "course_code": "Excel Yükleme",
        "course_name": fname,
        "exam_type": "Excel'den analiz",
        "n_items": n_items,
        "n_records": n_records,
        "booklets": [f"K{i+1}" for i in range(n_booklets)],
        "warnings": list(r.validation.warnings),
        "source": "excel",
        "fname": fname,
        "uploaded_by": str(user.pk),
        "uploaded_by_display": _uploader_display(user),
        "uploaded_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "n_students": n_records,
        "n_booklets": n_booklets,
    }

    upload_obj = KopyaUpload.objects.filter(upload_id=upload_id).first()
    if upload_obj is None:
        upload_obj = KopyaUpload(upload_id=upload_id, owner=user,
                                 original_filename=fname[:255], meta=meta)
        upload_obj.file.save(f"{upload_id}.xlsx", ContentFile(contents), save=False)
        upload_obj.save()
    elif upload_obj.owner_id != user.id:
        raise PermissionDenied("Bu yüklemeye erişim yetkiniz yok.")

    # Staging temizliği + oturum anahtarları
    try:
        os.unlink(stage_path)
    except OSError:
        pass
    request.session.pop(SESSION_UID, None)
    request.session.pop(SESSION_NAME, None)

    try:
        runner.trigger(upload_id, runner.DEFAULT_ALPHA, data)
    except Exception:  # noqa: BLE001 — panel yeniden dener ve hatayı gösterir
        logger.exception("Excel yüklemesi analizi başlatılamadı: %s", upload_id)

    return redirect("kopya:panel", source_id=upload_id)


@login_required
def template_xlsx(request):
    from kopya.excel_template import make_template_bytes
    resp = HttpResponse(
        make_template_bytes(n_items=20, n_booklets=1),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    resp["Content-Disposition"] = 'attachment; filename="kopya_analizi_sablon.xlsx"'
    return resp


# ── Panel ve çift detayı ──────────────────────────────────────────────────

def _pair_url_builder(source_id: str, alpha: float):
    qs = "?" + urlencode({"alpha": presenters.fmt_alpha(alpha)})

    def _url(copier: str, source: str):
        try:
            return reverse("kopya:pair_detail", args=[source_id, copier, source]) + qs
        except NoReverseMatch:
            return None
    return _url


@login_required
@never_cache
def dashboard(request, source_id):
    _check_source_access(request.user, source_id)
    alpha = presenters.parse_alpha(request.GET.get("alpha"))
    top_n = presenters.parse_top_n(request.GET.get("top_n"))
    try:
        out = runner.get_or_compute(source_id, alpha)
    except runner.SourceError as e:
        return _error(request, str(e))
    if not out.ready:
        return _computing(request, source_id, out.elapsed_s, f"Sınav: {source_id}")

    try:
        from kopya.engine.power_lookup import sensitivity_message
        sens_msg = sensitivity_message(out.result.n_valid, int(out.meta.get("n_items", 0)))
    except Exception:  # noqa: BLE001 — kaynakta da sessizce atlanıyordu
        sens_msg = ""

    base = reverse("kopya:panel", args=[source_id])
    alpha_s = presenters.fmt_alpha(alpha)

    def top_n_url(n: int) -> str:
        # Kaynak top_n değiştirirken alpha'yı düşürüyordu; burada korunur.
        return base + "?" + urlencode({"alpha": alpha_s, "top_n": n})

    ctx = presenters.dashboard_context(
        source_id, out.meta, out.result, alpha, top_n, sens_msg,
        pair_url=_pair_url_builder(source_id, alpha), top_n_url=top_n_url)
    return render(request, "kopya/dashboard.html", ctx)


@login_required
@never_cache
def pair_detail(request, source_id, copier, source):
    _check_source_access(request.user, source_id)
    alpha = presenters.parse_alpha(request.GET.get("alpha"))
    try:
        out = runner.get_or_compute(source_id, alpha)
    except runner.SourceError as e:
        return _error(request, str(e))
    if not out.ready:
        return _computing(request, source_id, out.elapsed_s, f"Çift: {copier} → {source}")

    back_url = (reverse("kopya:panel", args=[source_id]) + "?"
                + urlencode({"alpha": presenters.fmt_alpha(alpha)}))
    ctx = presenters.pair_context(out.data, out.result, copier, source, alpha)
    if ctx.get("error"):
        return _error(request, ctx["error"], status=404, back_url=back_url,
                      back_label="Panele dön")
    ctx.update({
        "source_id": source_id,
        "back_url": back_url,
        "course_code": out.meta.get("course_code", ""),
        "course_name": out.meta.get("course_name", ""),
    })
    return render(request, "kopya/pair.html", ctx)
