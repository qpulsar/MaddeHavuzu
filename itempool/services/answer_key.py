"""
Faz 13 — Otomatik cevap anahtarı ve öğrenme çıktısı başarı raporu servisleri.
"""


def generate_answer_key_from_form(test_form) -> str:
    """
    TestForm'daki FormItem'lar sırasına göre cevap anahtarı üretir.
    UploadSession.answer_key formatıyla uyumlu: 'ABCDA...' (sıralı doğru cevaplar)

    MCQ/TF için doğru seçeneğin label'ini alır.
    SHORT_ANSWER → expected_answer'ın ilk kelimesini alır (kısaltılmış).
    OPEN → '?' ile işaretlenir.
    """
    form_items = test_form.form_items.select_related(
        'item_instance__item'
    ).prefetch_related('item_instance__item__choices').order_by('order')

    key_chars = []
    for fi in form_items:
        item = fi.item_instance.item
        if item.item_type in ('MCQ', 'TF'):
            correct = item.choices.filter(is_correct=True).first()
            key_chars.append(correct.label if correct else '?')
        elif item.item_type == 'SHORT_ANSWER':
            key_chars.append('K')  # Kısa cevaplı → 'K' işareti
        else:
            key_chars.append('A')  # Açık uçlu → 'A' işareti

    return ''.join(key_chars)


def get_outcome_performance(upload_session) -> list[dict]:
    """
    UploadSession + test_form üzerinden her öğrenme çıktısı için başarı oranı hesaplar.

    Döndürür:
    [
        {
            'outcome': LearningOutcome instance,
            'question_count': int,
            'avg_correct_rate': float (0.0 - 1.0),
            'question_indices': [1, 3, 7, ...],  # formdaki soru numaraları
        },
        ...
    ]
    """
    test_form = upload_session.test_form
    if not test_form:
        return []

    from itempool.models import LearningOutcome

    # Her öğrenme çıktısı için bağlı soru indekslerini topla
    outcome_questions: dict[int, list[int]] = {}  # outcome_id → [soru order listesi]

    form_items = test_form.form_items.select_related(
        'item_instance'
    ).prefetch_related('item_instance__learning_outcomes').order_by('order')

    for fi in form_items:
        for outcome in fi.item_instance.learning_outcomes.all():
            outcome_questions.setdefault(outcome.id, []).append(fi.order)

    if not outcome_questions:
        return []

    # Tüm öğrenci sonuçlarındaki detailed_results'ı parse et
    # detailed_results formatı: "DYDBY..." (her karakter = D/Y/B/G)
    results = upload_session.results.all()
    student_count = results.count()
    if student_count == 0:
        return []

    # Soru bazında doğru yapan öğrenci sayısı
    question_correct: dict[int, int] = {}  # soru_order → doğru yapan öğrenci sayısı
    for result in results:
        detail = result.detailed_results or ''
        for i, char in enumerate(detail):
            q_order = i + 1  # 1-indexed
            if char == 'D':
                question_correct[q_order] = question_correct.get(q_order, 0) + 1

    # Outcome bazında hesapla
    outcomes = LearningOutcome.objects.filter(id__in=outcome_questions.keys())
    outcome_map = {o.id: o for o in outcomes}

    performance = []
    for outcome_id, q_orders in outcome_questions.items():
        total_correct = sum(question_correct.get(q, 0) for q in q_orders)
        max_possible = len(q_orders) * student_count
        avg_rate = (total_correct / max_possible) if max_possible > 0 else 0.0

        performance.append({
            'outcome': outcome_map.get(outcome_id),
            'question_count': len(q_orders),
            'avg_correct_rate': round(avg_rate, 4),
            'question_indices': sorted(q_orders),
        })

    # Başarı oranına göre sırala (düşükten yükseğe)
    performance.sort(key=lambda x: x['avg_correct_rate'])
    return performance
