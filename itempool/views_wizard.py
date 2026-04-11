"""
Sihirbaz (Wizard) view'ları:
  - Genel sihirbaz karşılama sayfası
  - Havuz kurulum sihirbazı (3 adım)
  - Sınav oluşturma sihirbazı (4 adım)
  - Değerlendirme sihirbazı (3 adım)
  - Global test formu listesi
"""

import random
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages

from itempool.models import (
    ItemPool, LearningOutcome, ItemInstance, TestForm, FormItem,
    ExamTemplate, Course,
)
from itempool.forms import ItemPoolForm, LearningOutcomeForm


# ─── Wizard Landing ───────────────────────────────────────────────────────────

@login_required
def wizard_landing(request):
    has_pools = ItemPool.objects.filter(owner=request.user).exists()
    has_forms = TestForm.objects.filter(created_by=request.user).exists()
    pool_count = ItemPool.objects.filter(owner=request.user).count()
    form_count = TestForm.objects.filter(created_by=request.user).count()
    course_count = Course.objects.filter(created_by=request.user).count()
    has_courses = course_count > 0
    return render(request, 'itempool/wizard/landing.html', {
        'has_pools': has_pools,
        'has_forms': has_forms,
        'has_courses': has_courses,
        'pool_count': pool_count,
        'form_count': form_count,
        'course_count': course_count,
    })


# ─── Havuz Sihirbazı ─────────────────────────────────────────────────────────

@login_required
def wizard_pool_step1(request):
    """Adım 1: Havuz temel bilgileri."""
    if request.method == 'POST':
        form = ItemPoolForm(request.POST)
        if form.is_valid():
            pool = form.save(commit=False)
            pool.owner = request.user
            pool.save()
            messages.success(request, f'"{pool.name}" havuzu oluşturuldu. Şimdi öğrenme çıktılarını ekleyin.')
            return redirect('itempool:wizard_pool_step2', pool_id=pool.pk)
    else:
        form = ItemPoolForm(initial={'status': 'ACTIVE'})
    return render(request, 'itempool/wizard/havuz_1.html', {'form': form})


@login_required
def wizard_pool_step2(request, pool_id):
    """Adım 2: Öğrenme çıktıları ekle."""
    pool = get_object_or_404(ItemPool, pk=pool_id, owner=request.user)
    outcomes = LearningOutcome.objects.filter(pool=pool).order_by('order')

    if request.method == 'POST':
        if 'delete_outcome' in request.POST:
            oid = request.POST.get('outcome_id')
            LearningOutcome.objects.filter(pk=oid, pool=pool).delete()
            return redirect('itempool:wizard_pool_step2', pool_id=pool.pk)

        if 'next' in request.POST:
            if not outcomes.exists():
                messages.warning(request, 'En az bir öğrenme çıktısı eklemeniz önerilir. Devam etmek için tekrar tıklayın.')
                request.session[f'wizard_pool_{pool_id}_skip_outcomes'] = True
            if outcomes.exists() or request.session.pop(f'wizard_pool_{pool_id}_skip_outcomes', False):
                return redirect('itempool:wizard_pool_step3', pool_id=pool.pk)

        # Yeni çıktı ekleme
        code = request.POST.get('code', '').strip()
        description = request.POST.get('description', '').strip()
        level = request.POST.get('level', 'KNOWLEDGE')
        if code and description:
            order = outcomes.count() + 1
            if LearningOutcome.objects.filter(pool=pool, code=code).exists():
                messages.error(request, f'"{code}" kodu bu havuzda zaten kullanılıyor.')
            else:
                LearningOutcome.objects.create(
                    pool=pool, code=code, description=description,
                    level=level, order=order, is_active=True,
                )
                return redirect('itempool:wizard_pool_step2', pool_id=pool.pk)
        elif 'add' in request.POST:
            messages.error(request, 'Kod ve açıklama alanları zorunludur.')

    bloom_levels = LearningOutcome._meta.get_field('level').choices
    return render(request, 'itempool/wizard/havuz_2.html', {
        'pool': pool,
        'outcomes': outcomes,
        'bloom_levels': bloom_levels,
        'step': 2,
    })


@login_required
def wizard_pool_step3(request, pool_id):
    """Adım 3: Soru ekleme yöntemini seç."""
    pool = get_object_or_404(ItemPool, pk=pool_id, owner=request.user)
    item_count = ItemInstance.objects.filter(pool=pool).count()

    if request.method == 'POST':
        method = request.POST.get('method')
        if method == 'manual':
            return redirect('itempool:item_create', pool_id=pool.pk)
        elif method == 'import':
            return redirect('itempool:import_upload', pool_id=pool.pk)
        else:
            return redirect('itempool:pool_detail', pk=pool.pk)

    return render(request, 'itempool/wizard/havuz_3.html', {
        'pool': pool,
        'item_count': item_count,
        'step': 3,
    })


# ─── Sınav Sihirbazı ─────────────────────────────────────────────────────────

@login_required
def wizard_exam_step1(request):
    """Adım 1: Sınav adı, havuz ve ders seç."""
    pools = ItemPool.objects.filter(owner=request.user, status=ItemPool.Status.ACTIVE)
    courses = Course.objects.filter(created_by=request.user).prefetch_related('pools')

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        pool_id = request.POST.get('pool_id')
        course_id = request.POST.get('course_id') or None
        if not name:
            messages.error(request, 'Sınav adı zorunludur.')
        elif not pool_id:
            messages.error(request, 'Havuz seçimi zorunludur.')
        else:
            pool = get_object_or_404(ItemPool, pk=pool_id, owner=request.user)
            tf = TestForm.objects.create(
                name=name,
                created_by=request.user,
                course_id=course_id,
                generation_metadata={'source_pool_id': pool.pk}
            )
            tf.pools.add(pool)
            return redirect('itempool:wizard_exam_step2', form_id=tf.pk)

    return render(request, 'itempool/wizard/sinav_1.html', {
        'pools': pools,
        'courses': courses,
        'step': 1,
    })


@login_required
def wizard_exam_step2(request, form_id):
    """Adım 2: Soru türü ve sayı belirleme + otomatik seçim."""
    tf = get_object_or_404(TestForm, pk=form_id, created_by=request.user)
    pool_id = tf.generation_metadata.get('source_pool_id')
    pool = get_object_or_404(ItemPool, pk=pool_id) if pool_id else None
    if not pool:
        messages.error(request, 'Bu form için kaynak havuz bilgisi bulunamadı.')
        return redirect('itempool:test_form_list_all')
    outcomes = LearningOutcome.objects.filter(pool=pool, is_active=True).order_by('order')
    courses = Course.objects.filter(created_by=request.user)

    # Her türden mevcut soru sayısı
    def avail(itype):
        return ItemInstance.objects.filter(pool=pool, item__item_type=itype).count()

    available = {
        'MCQ': avail('MCQ'),
        'TF': avail('TF'),
        'SHORT_ANSWER': avail('SHORT_ANSWER'),
        'OPEN': avail('OPEN'),
    }

    if request.method == 'POST':
        n_mcq  = max(0, int(request.POST.get('n_mcq', 0) or 0))
        n_tf   = max(0, int(request.POST.get('n_tf', 0) or 0))
        n_sa   = max(0, int(request.POST.get('n_sa', 0) or 0))
        n_open = max(0, int(request.POST.get('n_open', 0) or 0))
        pts_mcq  = max(1, int(request.POST.get('pts_mcq', 5) or 5))
        pts_tf   = max(1, int(request.POST.get('pts_tf', 5) or 5))
        pts_sa   = max(1, int(request.POST.get('pts_sa', 10) or 10))
        pts_open = max(1, int(request.POST.get('pts_open', 20) or 20))
        course_id = request.POST.get('course_id')

        if n_mcq + n_tf + n_sa + n_open == 0:
            messages.error(request, 'En az bir soru türü için sayı giriniz.')
        else:
            exclude_ids = set()
            if course_id:
                course = get_object_or_404(Course, pk=course_id, created_by=request.user)
                exclude_ids = course.get_applied_item_instance_ids()

            tf.form_items.all().delete()
            order = 1
            for itype, count, pts in [
                ('MCQ', n_mcq, pts_mcq),
                ('TF', n_tf, pts_tf),
                ('SHORT_ANSWER', n_sa, pts_sa),
                ('OPEN', n_open, pts_open),
            ]:
                qs = list(
                    ItemInstance.objects.filter(pool=pool, item__item_type=itype)
                    .exclude(id__in=exclude_ids)
                    .select_related('item')
                )
                random.shuffle(qs)
                for inst in qs[:count]:
                    FormItem.objects.create(
                        form=tf, item_instance=inst, order=order, points=pts
                    )
                    order += 1

            selected = tf.form_items.count()
            if selected == 0:
                messages.error(request, 'Havuzda yeterli soru bulunamadı.')
            else:
                messages.success(request, f'{selected} soru seçildi.')
                return redirect('itempool:wizard_exam_step3', form_id=tf.pk)

    return render(request, 'itempool/wizard/sinav_2.html', {
        'tf': tf,
        'pool': pool,
        'outcomes': outcomes,
        'available': available,
        'courses': courses,
        'default_course': tf.course,
        'step': 2,
    })


@login_required
def wizard_exam_step3(request, form_id):
    """Adım 3: Seçilen soruları gözden geçir, isteneni çıkar."""
    tf = get_object_or_404(TestForm, pk=form_id, created_by=request.user)
    form_items = FormItem.objects.filter(form=tf).order_by('order').select_related(
        'item_instance__item', 'item_instance__pool'
    )

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'remove':
            fi_id = request.POST.get('item_id')
            FormItem.objects.filter(pk=fi_id, form=tf).delete()
            # Sıralamayı düzelt
            for i, fi in enumerate(tf.form_items.order_by('order'), 1):
                if fi.order != i:
                    fi.order = i
                    fi.save(update_fields=['order'])
            return redirect('itempool:wizard_exam_step3', form_id=tf.pk)
        elif action == 'next':
            if not tf.form_items.exists():
                messages.error(request, 'Formda en az bir soru bulunmalıdır.')
            else:
                return redirect('itempool:wizard_exam_step4', form_id=tf.pk)
        elif action == 'back':
            return redirect('itempool:wizard_exam_step2', form_id=tf.pk)

    # Türe göre grupla
    by_type = {}
    type_labels = {'MCQ': 'Çoktan Seçmeli', 'TF': 'Doğru/Yanlış',
                   'SHORT_ANSWER': 'Kısa Cevaplı', 'OPEN': 'Açık Uçlu'}
    for fi in form_items:
        itype = fi.item_instance.item.item_type
        by_type.setdefault(itype, {'label': type_labels.get(itype, itype), 'items': []})
        by_type[itype]['items'].append(fi)

    return render(request, 'itempool/wizard/sinav_3.html', {
        'tf': tf,
        'form_items': form_items,
        'by_type': by_type,
        'total_points': sum(fi.points for fi in form_items),
        'step': 3,
    })


@login_required
def wizard_exam_step4(request, form_id):
    """Adım 4: Baskı şablonu seç, PDF indir."""
    tf = get_object_or_404(TestForm, pk=form_id, created_by=request.user)
    templates = ExamTemplate.objects.all()
    form_items = FormItem.objects.filter(form=tf).order_by('order').select_related('item_instance__item')
    total_points = sum(fi.points for fi in form_items)

    return render(request, 'itempool/wizard/sinav_4.html', {
        'tf': tf,
        'templates': templates,
        'form_items': form_items,
        'total_points': total_points,
        'step': 4,
    })


# ─── Değerlendirme Sihirbazı ─────────────────────────────────────────────────

@login_required
def wizard_eval_step1(request):
    """Adım 1: Sınav formu seç."""
    forms_qs = (
        TestForm.objects.filter(created_by=request.user)
        .prefetch_related('form_items')
        .order_by('-id')
    )

    if request.method == 'POST':
        form_id = request.POST.get('form_id')
        if not form_id:
            messages.error(request, 'Sınav formu seçimi zorunludur.')
        else:
            return redirect('itempool:wizard_eval_step2', form_id=form_id)

    return render(request, 'itempool/wizard/degerlendirme_1.html', {
        'forms': forms_qs,
        'step': 1,
    })


@login_required
def wizard_eval_step2(request, form_id):
    """Adım 2: Cevap anahtarını doğrula + optik okuma yönlendirmesi."""
    tf = get_object_or_404(TestForm, pk=form_id, created_by=request.user)
    from itempool.services.answer_key import generate_answer_key_from_form
    answer_key = generate_answer_key_from_form(tf)
    from grading.models import FileFormatConfig, UploadSession
    file_formats = FileFormatConfig.objects.all()
    # Bu forma ait mevcut oturumlar
    existing_sessions = UploadSession.objects.filter(
        test_form=tf, owner=request.user
    ).order_by('-created_at')[:5]

    return render(request, 'itempool/wizard/degerlendirme_2.html', {
        'tf': tf,
        'answer_key': answer_key,
        'file_formats': file_formats,
        'existing_sessions': existing_sessions,
        'step': 2,
    })


@login_required
def wizard_eval_step3(request, session_id):
    """Adım 3: Yükleme sonuçları ve öğrenme çıktısı raporu."""
    from grading.models import UploadSession
    session = get_object_or_404(UploadSession, pk=session_id, owner=request.user)
    from itempool.services.answer_key import get_outcome_performance
    performance = get_outcome_performance(session)

    return render(request, 'itempool/wizard/degerlendirme_3.html', {
        'session': session,
        'performance': performance,
        'step': 3,
    })


# ─── Global Test Form Listesi ─────────────────────────────────────────────────

@login_required
def test_form_list_all(request):
    """Tüm test formlarını listeler."""
    user = request.user
    if user.is_staff or (hasattr(user, 'profile') and user.profile.role == 'ADMIN'):
        forms_qs = (
            TestForm.objects.all()
            .prefetch_related('form_items')
            .order_by('-id')
        )
    else:
        forms_qs = (
            TestForm.objects.filter(created_by=request.user)
            .prefetch_related('form_items')
            .order_by('-id')
        )
    return render(request, 'itempool/test_form_list_all.html', {'forms': forms_qs})
