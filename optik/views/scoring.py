"""
Puanlama (sihirbaz 5. adım), dışa aktarma ve onay view'ları.

Kaynak: omr_analysis/routes.py
- test_scoring       ← test_scoring_page          (2988)
- approve_form       ← batch_approve_form         (3634)
- approve            ← batch_approve              (3683)
- snapshot_detail    ← snapshot_view              (3715)
- batch_score_page   ← batch_score_page           (5437)
- do_scoring         ← batch_do_scoring           (5654)
- open_scoring       ← batch_open_scoring_page    (5759)
- save_open_scores   ← batch_save_open_scores     (5890)
- batch_scores       ← batch_scores_page          (5955)
- student_score      ← student_score_detail       (6179)
- export_scores      ← batch_export_scores        (6730)

Farklar:
- Her view giriş + sahiplik kontrolü yapar (kaynakta yoktu).
- do_scoring'deki sınav süresi (deadline) kontrolü kaldırıldı: bu projede
  sınav takvimi yok.
- Puan tablosunda form görüntüsü, öğrenci no → kayıt eşlemesi yerine doğrudan
  puanlama kaydındaki record_id ile açılır (mükerrer numaralarda doğru form).
"""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST

from optik import store
from optik.permissions import get_batch_for_user, get_test_for_user
from optik.services import core as service
from optik.services import export as export_service
from optik.services import scoring as scoring_service
from optik.services import snapshot as snapshot_service
from optik.services.omr import detect_duplicate_students
from optik.views.records import base_context, q_sort_key
from optik.wizard import wizard_context

EXPORT_CONTENT_TYPES = {
    "tsv": "text/tab-separated-values; charset=utf-8",
    "csv": "text/csv; charset=utf-8",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}
EXPORT_FUNCS = {
    "tsv": export_service.export_to_tsv,
    "csv": export_service.export_to_csv,
    "xlsx": export_service.export_to_xlsx,
}

ITEM_STATUS_CLASS = {
    "correct": "optik-cell-correct",
    "wrong": "optik-cell-wrong",
    "multi": "optik-cell-wrong",
    "blank": "optik-cell-blank",
}

# Öğrenci puan detayı: durum → (etiket, ikon, metin sınıfı, satır sınıfı)
STUDENT_ITEM_STATUS = {
    "correct": ("Doğru", "bi-check-lg", "text-success fw-semibold", "optik-cell-correct"),
    "wrong": ("Yanlış", "bi-x-lg", "text-danger fw-semibold", "optik-cell-wrong"),
    "blank": ("Boş", "bi-dash", "text-muted", "optik-cell-blank"),
    "multi": ("Çoklu", "bi-exclamation-lg", "text-warning fw-semibold", "optik-cell-multi"),
    "not_graded": ("Puansız", "bi-dash", "text-muted", "optik-cell-blank"),
}


# ── Yardımcılar ─────────────────────────────────────────────────────────


def _message_page(request, ctx: dict, title: str, heading: str, text: str = "",
                  links=None, level: str = "info", status: int = 200):
    """Kaynaktaki kısa uyarı/hata sayfalarının karşılığı."""
    ctx = dict(ctx)
    ctx.update({'page_title': title, 'heading': heading, 'text': text,
                'links': links or [], 'level': level})
    return render(request, 'optik/scoring/message.html', ctx, status=status)


def _batch_ctx(batch_obj) -> tuple:
    batch = service.get_batch(batch_obj.batch_id)
    test = service.get_test(batch_obj.test.test_id)
    return batch, test, base_context(test, batch)


def class_stats_tiles(class_stats: dict, record_count: int) -> list:
    return [
        {'value': class_stats.get("mean", 0), 'label': "Ortalama"},
        {'value': class_stats.get("max", 0), 'label': "En Yüksek"},
        {'value': class_stats.get("min", 0), 'label': "En Düşük"},
        {'value': f"{class_stats.get('pass_count', 0)}/{record_count}", 'label': "Geçen/Toplam"},
    ]


def export_links(batch_id: str) -> list:
    """İndir menüsü: [(başlık, [(etiket, url), ...]), ...]."""
    base = reverse('optik:export_scores', args=[batch_id])
    groups = []
    for title, detail in (("Özet", 0), ("Detaylı (Tüm Maddeler)", 1)):
        groups.append({'title': title, 'links': [
            {'label': label, 'icon': icon, 'url': f"{base}?fmt={fmt}&detail={detail}"}
            for fmt, label, icon in (("tsv", "TSV", "bi-file-earmark-text"),
                                     ("csv", "CSV", "bi-filetype-csv"),
                                     ("xlsx", "Excel", "bi-file-earmark-excel"))
        ]})
    return groups


def build_score_table(score_records: list, all_records: list) -> dict:
    """
    Puanlama sonuç tablosu: öğrenci no'ya göre sıralı satırlar, madde bazında
    puan hücreleri (durum rengiyle) ve mükerrer numaralar.
    """
    score_records = sorted(score_records, key=lambda x: str(x.get("student_no") or ""))

    sno_counts = {}
    for rec in score_records:
        sno = rec.get("student_no", "")
        if sno:
            sno_counts[sno] = sno_counts.get(sno, 0) + 1
    dup_snos = {sno for sno, cnt in sno_counts.items() if cnt > 1}

    # Görüntü için: puanlama kaydında record_id yoksa öğrenci no ile eşle
    existing_ids = {r.get("record_id") for r in all_records}
    sno_to_rid = {r.get("student_no"): r.get("record_id") for r in all_records if r.get("student_no")}

    sample_items = score_records[0].get("item_scores", {}) if score_records else {}
    item_ids = sorted(sample_items.keys(), key=q_sort_key)

    rows = []
    for idx, rec in enumerate(score_records, 1):
        sno = rec.get("student_no", "")
        summary = rec.get("summary", {}) or {}
        iscores = rec.get("item_scores", {}) or {}
        rid = rec.get("record_id")
        if rid not in existing_ids:
            rid = sno_to_rid.get(sno, "")
        cells = []
        for iid in item_ids:
            item = iscores.get(iid, {}) or {}
            cells.append({'points': item.get("points", 0),
                          'css': ITEM_STATUS_CLASS.get(item.get("status", ""), "")})
        rows.append({
            'idx': idx,
            'student_no': sno,
            'booklet': rec.get("booklet", ""),
            'total': summary.get("total_points", 0),
            'passed': (summary.get("percentage", 0) or 0) >= 50,
            'is_dup': sno in dup_snos,
            'record_id': rid,
            'cells': cells,
        })
    return {'rows': rows, 'item_ids': item_ids, 'dup_snos': sorted(dup_snos)}


def open_items_for_test(test: dict, fallback: bool = True) -> list:
    """
    Açık uçlu maddeler [{"item_id", "points"}]. items'da OPEN tanımlı değilse
    (fallback=True) question_counts'tan MCQ'ların ardından üretilir.
    """
    items = test.get("items", {}) or {}
    question_counts = test.get("question_counts", {}) or {}
    open_count = question_counts.get("OPEN", 0) or 0
    mcq_count = question_counts.get("MCQ", 0) or 0

    open_items = [{"item_id": iid, "points": data.get("points", 0)}
                  for iid, data in items.items() if data.get("type") == "OPEN"]
    open_items.sort(key=lambda x: q_sort_key(x["item_id"]))

    if fallback and not open_items and open_count > 0:
        open_total = (test.get("points_by_type_total", {}) or {}).get("OPEN", 0) or 0
        per_open = open_total / open_count
        open_items = [{"item_id": f"Q{mcq_count + 1 + i}", "points": per_open}
                      for i in range(open_count)]
    return open_items


def open_score_rows(records: list, open_items: list) -> list:
    """Açık uçlu puan giriş tablosu satırları (input adı: <record_id>_<Qn>)."""
    rows = []
    for idx, rec in enumerate(records):
        rid = rec.get("record_id", "")
        current = rec.get("open_scores", {}) or {}
        rows.append({
            'student_no': rec.get("student_no") or f"Kayıt-{idx + 1}",
            'cells': [{'name': f"{rid}_{it['item_id']}",
                       'value': current.get(it["item_id"], ""),
                       'max': it["points"]} for it in open_items],
        })
    return rows


def parse_open_scores(post, record_id: str, open_items: list) -> tuple:
    """Formdan bir kaydın açık uçlu puanlarını oku; 0..max aralığına kırp."""
    open_scores = {}
    open_total = 0
    for item in open_items:
        value = post.get(f"{record_id}_{item['item_id']}", "")
        if value and str(value).strip():
            try:
                score = float(value)
            except ValueError:
                continue
            score = max(min(score, item["points"]), 0)
            open_scores[item["item_id"]] = score
            open_total += score
    return open_scores, open_total


def scoring_mode(test: dict) -> dict:
    question_counts = test.get("question_counts", {}) or {}
    return {'open_count': question_counts.get("OPEN", 0) or 0,
            'mcq_count': question_counts.get("MCQ", 0) or 0}


def missing_answer_keys(test: dict, records: list) -> list:
    answer_keys = test.get("answer_keys", {}) or {}
    booklets = test.get("booklets", []) or []
    record_booklets = {r.get("booklet") for r in records if r.get("booklet")}
    if not record_booklets and len(booklets) == 1:
        record_booklets = set(booklets)
    return sorted(b for b in record_booklets if b not in answer_keys)


# ── Test-merkezli puanlama sayfası ──────────────────────────────────────

@login_required
@require_GET
def test_scoring(request, test_id):
    """Puanlama - sihirbaz 5. adım: sonuç tablosu veya puanlama formu."""
    get_test_for_user(request.user, test_id)
    test = service.get_test(test_id)
    batch_id = service.get_test_batch_id(test_id)

    ctx = base_context(test)
    ctx.update(wizard_context(test_id, 5))
    if not batch_id:
        ctx.update({'empty_heading': "Önce form yükleyin"})
        return render(request, 'optik/scoring/form.html', ctx)
    ctx['batch_id'] = batch_id

    existing_scores = scoring_service.get_batch_scores(batch_id)
    if existing_scores and existing_scores.get("records") and not request.GET.get("rescore"):
        batch = service.get_batch(batch_id)
        score_records = existing_scores.get("records", [])
        ctx.update(build_score_table(score_records, service.get_batch_records(batch_id)))
        ctx.update({
            'batch': batch,
            'stats': class_stats_tiles(existing_scores.get("class_statistics", {}) or {},
                                       len(score_records)),
            'export_groups': export_links(batch_id),
        })
        return render(request, 'optik/scoring/results.html', ctx)

    # --- Puanlama formu ---
    records = service.get_batch_records(batch_id)
    if not records:
        ctx.update({'empty_heading': "Önce form yükleyin"})
        return render(request, 'optik/scoring/form.html', ctx)

    missing = missing_answer_keys(test, records)
    if missing:
        ctx['missing_keys'] = missing
        return render(request, 'optik/scoring/form.html', ctx)

    mode = scoring_mode(test)
    open_count, mcq_count = mode['open_count'], mode['mcq_count']
    if mcq_count > 0 and open_count > 0:
        info_text = f"MCQ: {mcq_count} soru (otomatik) + Açık Uçlu: {open_count} soru (manuel)"
        submit_text = "Puanlamayı Başlat"
    elif open_count > 0:
        info_text = f"Açık Uçlu: {open_count} soru (manuel puan girişi)"
        submit_text = "Puanları Kaydet"
    else:
        info_text = f"MCQ: {mcq_count} soru (otomatik puanlama)"
        submit_text = "Puanlamayı Başlat"

    open_items = open_items_for_test(test) if open_count > 0 else []
    ctx.update({
        'records_count': len(records),
        'info_text': info_text,
        'submit_text': submit_text,
        'open_count': open_count,
        'open_items': open_items,
        'open_rows': open_score_rows(records, open_items) if open_items else [],
        'duplicates': [d["student_no"] for d in detect_duplicate_students(batch_id)],
        'show_form': True,
    })
    return render(request, 'optik/scoring/form.html', ctx)


@login_required
@require_POST
def do_scoring(request, batch_id):
    """Puanlama işlemi: açık uçlu puanları kaydet → MCQ otomatik puanla → toplamları güncelle."""
    batch_obj = get_batch_for_user(request.user, batch_id)
    batch, test, ctx = _batch_ctx(batch_obj)
    open_count = scoring_mode(test)['open_count']

    try:
        # 1) Önce açık uçlu puanları kaydet
        if open_count > 0:
            open_items = open_items_for_test(test)
            for rec in service.get_batch_records(batch_id):
                record_id = rec.get("record_id", "")
                open_scores, open_total = parse_open_scores(request.POST, record_id, open_items)
                rec["open_scores"] = open_scores
                rec["open_total"] = open_total
                service.save_record(batch_id, record_id, rec)

        # 2) MCQ otomatik puanlama
        scoring_service.score_batch(batch_id, request.user)

        # 3) Açık uçlu puanları toplam skora ekle
        if open_count > 0:
            scoring_service.update_scores_json(batch_id)
    except (ValueError, store.NotFound) as e:
        return _message_page(
            request, ctx, "Puanlama Hatası", "Puanlama Hatası", str(e), level="danger",
            links=[("Puanlama Sayfasına Dön", reverse('optik:batch_score', args=[batch_id])),
                   ("Batch Detay", reverse('optik:batch_detail', args=[batch_id]))],
            status=400)

    return redirect('optik:scoring', test_id=batch["test_id"])


# ── Açık uçlu puan girişi ───────────────────────────────────────────────

@login_required
@require_GET
def open_scoring(request, batch_id):
    """Açık uçlu soru puan girişi sayfası."""
    batch_obj = get_batch_for_user(request.user, batch_id)
    batch, test, ctx = _batch_ctx(batch_obj)

    if scoring_mode(test)['open_count'] == 0:
        return redirect('optik:scoring', test_id=batch["test_id"])

    records = service.get_batch_records(batch_id)
    open_items = open_items_for_test(test, fallback=False)
    ctx.update({
        'records_count': len(records),
        'open_items': open_items,
        'open_rows': open_score_rows(records, open_items),
    })
    return render(request, 'optik/scoring/open_scoring.html', ctx)


@login_required
@require_POST
def save_open_scores(request, batch_id):
    """Açık uçlu puanları kaydet ve toplam puanları güncelle."""
    batch_obj = get_batch_for_user(request.user, batch_id)
    batch, test, _ctx = _batch_ctx(batch_obj)
    open_items = open_items_for_test(test, fallback=False)

    for rec in service.get_batch_records(batch_id):
        record_id = rec.get("record_id", "")
        open_scores, open_total = parse_open_scores(request.POST, record_id, open_items)
        rec["open_scores"] = open_scores
        rec["open_total"] = open_total
        # Toplam puanı yeniden hesapla (kaynaktaki gibi kayıt üzerinde)
        mcq_score = rec.get("mcq_score", 0) or rec.get("total_score", 0) or 0
        rec["total_score"] = mcq_score + open_total
        service.save_record(batch_id, record_id, rec)

    # Puanlama sonucunu da güncelle
    scoring_service.update_scores_json(batch_id)
    return redirect('optik:scoring', test_id=batch["test_id"])


# ── Batch puanlama sayfaları (sihirbaz öncesi) ──────────────────────────

@login_required
@require_GET
def batch_score_page(request, batch_id):
    """Batch puanlama sayfası."""
    batch_obj = get_batch_for_user(request.user, batch_id)
    batch, test, ctx = _batch_ctx(batch_obj)
    detail_url = reverse('optik:batch_detail', args=[batch_id])

    records = service.get_batch_records(batch_id)
    if not records:
        return _message_page(
            request, ctx, "Puanlama", "Önce form yüklemelisiniz", level="warning",
            links=[("Form Yükle", reverse('optik:upload_forms', args=[batch_obj.test.test_id])),
                   ("Geri", detail_url)])

    booklets = test.get("booklets", []) or []
    record_booklets = {r.get("booklet") for r in records if r.get("booklet")}
    unprocessed = [r for r in records if not r.get("booklet")]
    if unprocessed and not record_booklets and len(booklets) != 1:
        return _message_page(
            request, ctx, "Puanlama", "Formlar Henüz İşlenmemiş",
            "Yüklenen formlar henüz OMR ile taranmamış. Önce formları işlemeniz gerekiyor.",
            level="warning", links=[("Batch Detay", detail_url)])

    missing = missing_answer_keys(test, records)
    if missing:
        return _message_page(
            request, ctx, "Puanlama", "Cevap Anahtarı Eksik",
            "Şu kitapçıklar için cevap anahtarı bulunamadı: " + ", ".join(missing),
            level="warning",
            links=[("Cevap Anahtarı Gir", reverse('optik:answer_key', args=[test["test_id"]])),
                   ("Geri", detail_url)])

    mode = scoring_mode(test)
    open_count, mcq_count = mode['open_count'], mode['mcq_count']
    n = len(records)
    if mcq_count > 0 and open_count > 0:
        title = "Puanlama (MCQ + Açık Uçlu)"
        info_items = [f"Toplam {n} kayıt puanlanacak",
                      f"Çoktan seçmeli (MCQ): {mcq_count} soru - Otomatik puanlanır",
                      f"Açık uçlu (OPEN): {open_count} soru - Aşağıdan manuel puan giriniz"]
        submit_text = "Puanlamayı Başlat (MCQ Otomatik + Açık Uçlu Manuel)"
    elif open_count > 0:
        title = "Puanlama (Açık Uçlu)"
        info_items = [f"Toplam {n} kayıt puanlanacak",
                      f"Açık uçlu (OPEN): {open_count} soru - Aşağıdan manuel puan giriniz"]
        submit_text = "Puanları Kaydet ve Hesapla"
    else:
        title = "Otomatik Puanlama"
        info_items = [f"Toplam {n} kayıt puanlanacak",
                      f"Çoktan seçmeli (MCQ): {mcq_count} soru - Otomatik puanlanır",
                      "Doğru/Yanlış/Boş sayıları hesaplanacak"]
        submit_text = "Puanlamayı Başlat"

    open_items = open_items_for_test(test) if open_count > 0 else []
    ctx.update({
        'title': title,
        'info_items': info_items,
        'submit_text': submit_text,
        'open_count': open_count,
        'open_items': open_items,
        'open_rows': open_score_rows(records, open_items) if open_items else [],
    })
    return render(request, 'optik/scoring/batch_score.html', ctx)


@login_required
@require_GET
def batch_scores(request, batch_id):
    """Puanlama sonuçları (puana göre sıralı)."""
    batch_obj = get_batch_for_user(request.user, batch_id)
    batch, test, ctx = _batch_ctx(batch_obj)

    scores = scoring_service.get_batch_scores(batch_id)
    if not scores:
        return _message_page(
            request, ctx, "Puanlama Sonuçları", "Henüz puanlama yapılmamış", level="warning",
            links=[("Puanlama Yap", reverse('optik:batch_score', args=[batch_id])),
                   ("Geri", reverse('optik:batch_detail', args=[batch_id]))])

    records = sorted(scores.get("records", []),
                     key=lambda x: (x.get("summary", {}) or {}).get("total_points", 0), reverse=True)
    rows = []
    for idx, rec in enumerate(records, 1):
        s = rec.get("summary", {}) or {}
        rows.append({
            'idx': idx, 'student_no': rec.get("student_no", ""), 'booklet': rec.get("booklet", ""),
            'correct': s.get("correct", 0), 'wrong': s.get("wrong", 0), 'blank': s.get("blank", 0),
            'total': s.get("total_points", 0), 'percentage': s.get("percentage", 0),
            'passed': (s.get("percentage", 0) or 0) >= 50,
        })
    ctx.update({
        'rows': rows,
        'stats': class_stats_tiles(scores.get("class_statistics", {}) or {}, len(records)),
        'export_groups': export_links(batch_id),
    })
    return render(request, 'optik/scoring/batch_scores.html', ctx)


@login_required
@require_GET
def student_score(request, batch_id, student_no):
    """Öğrenci puan detayı - madde bazında sonuç."""
    batch_obj = get_batch_for_user(request.user, batch_id)
    batch, test, ctx = _batch_ctx(batch_obj)

    student = scoring_service.get_student_score(batch_id, student_no)
    if not student:
        return _message_page(
            request, ctx, "Puan Detay", f"Öğrenci bulunamadı: {student_no}", level="warning",
            links=[("Puanlama Sonuçları", reverse('optik:batch_scores', args=[batch_id]))],
            status=404)

    item_rows = []
    for item_id, item in sorted((student.get("item_scores", {}) or {}).items(),
                                key=lambda x: q_sort_key(x[0])):
        status = item.get("status", "")
        label, icon, text_cls, row_cls = STUDENT_ITEM_STATUS.get(status, (status, "", "", ""))
        item_rows.append({
            'item_id': item_id,
            'student_answer': item.get("student_answer", "") or "—",
            'correct_answer': item.get("correct_answer", "") or "—",
            'label': label, 'icon': icon, 'text_cls': text_cls, 'row_cls': row_cls,
            'points': item.get("points", 0), 'max_points': item.get("max_points", 0),
        })

    summary = student.get("summary", {}) or {}
    ctx.update({
        'student_no': student_no,
        'booklet': student.get("booklet", ""),
        'summary': summary,
        'passed': (summary.get("percentage", 0) or 0) >= 50,
        'item_rows': item_rows,
    })
    return render(request, 'optik/scoring/student_score.html', ctx)


@login_required
@require_GET
def export_scores(request, batch_id):
    """Puanları dışa aktar. ?fmt=tsv|csv|xlsx&detail=0|1"""
    get_batch_for_user(request.user, batch_id)

    fmt = (request.GET.get("fmt") or "tsv").lower()
    if fmt not in EXPORT_FUNCS:
        return HttpResponse("Geçersiz format! tsv, csv veya xlsx kullanın.", status=400,
                            content_type="text/plain; charset=utf-8")
    try:
        detail = int(request.GET.get("detail", 0))
    except (TypeError, ValueError):
        detail = 0
    if detail not in (0, 1):
        detail = 0

    content = EXPORT_FUNCS[fmt](batch_id, detail)
    filename = export_service.get_export_filename(batch_id, fmt, detail)
    response = HttpResponse(content, content_type=EXPORT_CONTENT_TYPES[fmt])
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


# ── Onay + snapshot ─────────────────────────────────────────────────────

@login_required
@require_GET
def approve_form(request, batch_id):
    """Batch onaylama formu."""
    batch_obj = get_batch_for_user(request.user, batch_id)
    _batch, _test, ctx = _batch_ctx(batch_obj)
    return render(request, 'optik/scoring/approve_form.html', ctx)


@login_required
@require_POST
def approve(request, batch_id):
    """Batch'i onayla ve snapshot al."""
    get_batch_for_user(request.user, batch_id)
    reason = request.POST.get("reason", "").strip()
    version = snapshot_service.create_snapshot(batch_id, request.user, reason or "Batch approved")
    service.approve_batch(batch_id, request.user)
    messages.success(request, f"Batch onaylandı ve {version} snapshot oluşturuldu!")
    return redirect('optik:batch_detail', batch_id=batch_id)


@login_required
@require_GET
def snapshot_detail(request, batch_id, version):
    """Snapshot görüntüle (ilk 20 kayıt)."""
    batch_obj = get_batch_for_user(request.user, batch_id)
    try:
        snapshot = snapshot_service.get_snapshot(batch_id, version)
    except store.NotFound:
        raise Http404("Snapshot bulunamadı")
    _batch, _test, ctx = _batch_ctx(batch_obj)

    metadata = snapshot["metadata"]
    records = snapshot["records"]
    rows = []
    for rec in records[:20]:
        eff = rec.get("effective", {}) or {}
        rows.append({
            'student_no': eff.get("student_no", ""),
            'booklet': eff.get("booklet", ""),
            'seating': (eff.get("seating") or {}).get("cell_id", ""),
            'has_overrides': bool(rec.get("has_overrides")),
        })
    ctx.update({
        'version': version,
        'created_at': str(metadata.get("created_at", ""))[:19].replace("T", " "),
        'created_by': service.user_display_name(metadata.get("created_by")),
        'reason': metadata.get("reason", ""),
        'record_count': metadata.get("record_count", 0),
        'rows': rows,
        'remaining': max(len(records) - 20, 0),
    })
    return render(request, 'optik/scoring/snapshot.html', ctx)
