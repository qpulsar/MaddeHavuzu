
addon = """

# ============================================================
# Faz 27 — Sinav Formu ↔ Optik Okuma Entegrasyonu (Grading Hub)
# ============================================================


@login_required
def exam_form_upload(request, pk):
    \"\"\"Bir TestForm icin optik okuma yukleme sayfasi.\"\"\"
    from grading.models import FileFormatConfig, UploadSession
    from .services.answer_key import generate_answer_key_from_form

    test_form = get_object_or_404(TestForm, pk=pk)
    answer_key = generate_answer_key_from_form(test_form)
    formats = FileFormatConfig.objects.filter(is_active=True)
    default_format = formats.filter(is_default=True).first() or formats.first()
    existing_sessions = UploadSession.objects.filter(
        test_form=test_form, owner=request.user
    ).order_by('-created_at')
    applications = []
    if test_form.course:
        applications = list(test_form.course.exam_applications.filter(test_form=test_form))
    return render(request, 'itempool/exam_form_upload.html', {
        'test_form': test_form,
        'answer_key': answer_key,
        'question_count': len(answer_key),
        'formats': formats,
        'default_format': default_format,
        'existing_sessions': existing_sessions,
        'applications': applications,
    })


@login_required
def exam_grading_hub(request, pk, session_pk=None):
    \"\"\"Bir TestForm icin merkezi analiz paneli.\"\"\"
    from grading.models import UploadSession
    from grading.services.statistics import StatisticsService
    from grading.services.analysis import CheatingAnalysisService
    from .services.answer_key import get_outcome_performance

    test_form = get_object_or_404(TestForm, pk=pk)
    sessions = UploadSession.objects.filter(test_form=test_form).order_by('-created_at')
    active_session = None
    if session_pk:
        active_session = get_object_or_404(UploadSession, pk=session_pk, test_form=test_form)
    elif sessions.exists():
        active_session = sessions.first()

    active_tab = request.GET.get('tab', 'stats')
    stats = None
    item_analysis = None
    kr20 = None
    alpha = None
    cheating = None
    outcome_performance = None
    histogram_labels = []

    if active_session and active_session.is_processed:
        svc = StatisticsService()
        if active_tab == 'stats':
            stats = svc.calculate_session_stats(active_session)
            if stats:
                histogram_labels = [str(i) for i in range(len(stats['histogram_bins']))]
                for item in stats['item_analysis']:
                    item['is_problematic'] = item['r'] < 0.20 or item['p'] < 0.10 or item['p'] > 0.95
        elif active_tab == 'items':
            stats = svc.calculate_session_stats(active_session)
            if stats:
                item_analysis = stats['item_analysis']
                fi_map = {fi.order: fi for fi in test_form.form_items.select_related('item_instance__item')}
                for item in item_analysis:
                    item['is_problematic'] = item['r'] < 0.20 or item['p'] < 0.10 or item['p'] > 0.95
                    item['form_item'] = fi_map.get(item['question_number'])
        elif active_tab == 'kr20':
            kr20 = svc.calculate_kr20(active_session)
        elif active_tab == 'alpha':
            alpha = svc.calculate_cronbach_alpha(active_session)
        elif active_tab == 'cheating':
            cheating = CheatingAnalysisService(active_session).analyze()
        elif active_tab == 'outcomes':
            outcome_performance = get_outcome_performance(active_session)

    return render(request, 'itempool/exam_grading_hub.html', {
        'test_form': test_form,
        'sessions': sessions,
        'active_session': active_session,
        'active_tab': active_tab,
        'stats': stats,
        'item_analysis': item_analysis,
        'kr20': kr20,
        'alpha': alpha,
        'cheating': cheating,
        'outcome_performance': outcome_performance,
        'histogram_labels': histogram_labels,
    })


@login_required
def exam_grading_hub_standalone(request, session_pk):
    \"\"\"Standalone mod - sadece UploadSession bazli analiz.\"\"\"
    from grading.models import UploadSession
    from grading.services.statistics import StatisticsService
    from grading.services.analysis import CheatingAnalysisService

    session = get_object_or_404(UploadSession, pk=session_pk, owner=request.user)
    active_tab = request.GET.get('tab', 'stats')
    stats = None
    item_analysis = None
    kr20 = None
    alpha = None
    cheating = None
    histogram_labels = []

    if session.is_processed:
        svc = StatisticsService()
        if active_tab == 'stats':
            stats = svc.calculate_session_stats(session)
            if stats:
                histogram_labels = [str(i) for i in range(len(stats['histogram_bins']))]
                for item in stats['item_analysis']:
                    item['is_problematic'] = item['r'] < 0.20 or item['p'] < 0.10 or item['p'] > 0.95
        elif active_tab == 'items':
            stats = svc.calculate_session_stats(session)
            if stats:
                item_analysis = stats['item_analysis']
                for item in item_analysis:
                    item['is_problematic'] = item['r'] < 0.20 or item['p'] < 0.10 or item['p'] > 0.95
        elif active_tab == 'kr20':
            kr20 = svc.calculate_kr20(session)
        elif active_tab == 'alpha':
            alpha = svc.calculate_cronbach_alpha(session)
        elif active_tab == 'cheating':
            cheating = CheatingAnalysisService(session).analyze()

    user_forms = TestForm.objects.filter(created_by=request.user).order_by('-created_at')[:20]
    return render(request, 'itempool/exam_grading_hub_standalone.html', {
        'session': session,
        'active_tab': active_tab,
        'stats': stats,
        'item_analysis': item_analysis,
        'kr20': kr20,
        'alpha': alpha,
        'cheating': cheating,
        'histogram_labels': histogram_labels,
        'user_forms': user_forms,
    })


@login_required
def bind_session_to_form(request, session_pk):
    \"\"\"Bir UploadSession u bir TestForm a baglar.\"\"\"
    from grading.models import UploadSession

    session = get_object_or_404(UploadSession, pk=session_pk, owner=request.user)
    if request.method != 'POST':
        return redirect('itempool:exam_grading_hub_standalone', session_pk=session_pk)

    test_form_id = request.POST.get('test_form_id')
    if not test_form_id:
        messages.error(request, 'Sinav formu secimi zorunludur.')
        return redirect('itempool:exam_grading_hub_standalone', session_pk=session_pk)

    test_form = get_object_or_404(TestForm, pk=test_form_id)
    session.test_form = test_form
    session.save(update_fields=['test_form'])

    try:
        from itempool.services.analysis_service import ItemAnalysisService
        item_mapping = {fi.order - 1: fi.item_instance_id for fi in test_form.form_items.order_by('order')}
        count = ItemAnalysisService().process_session_results(session, item_mapping, test_form)
        if count > 0:
            messages.success(request, f'Forma baglandi ve {count} madde analizi kaydedildi.')
        else:
            messages.success(request, 'Oturum forma basariyla baglandi.')
    except Exception as e:
        messages.warning(request, f'Baglama yapildi ancak madde analizi: {e}')

    return redirect('itempool:exam_grading_hub_session', pk=test_form.pk, session_pk=session_pk)
"""

with open('itempool/views.py', 'a', encoding='utf-8') as f:
    f.write(addon)

print('DONE - views appended successfully')
