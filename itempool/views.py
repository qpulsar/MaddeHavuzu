from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView, DetailView, CreateView, UpdateView
from django.urls import reverse_lazy
from django.contrib import messages
from django.db import transaction
from django.db.models import Q
from django.core.paginator import Paginator

from .models import (
    ItemPool, LearningOutcome, Item, ItemInstance, ImportBatch, DraftItem, ItemChoice, OutcomeSuggestion,
    TestForm, FormItem, Blueprint, PoolPermission, ItemAuditLog, Course, CourseSpecTable, ExamApplication, ExamTemplate
)
from .mixins import PoolAccessMixin
from .forms import (
    ItemPoolForm, LearningOutcomeForm, ItemForm, ItemChoiceFormSet, TestFormForm, BlueprintForm,
    CourseForm, CourseSpecTableForm, TestFormCreateForm, ExamApplicationForm
)
from .services.import_docx import DocxImportService
from .services.llm_client import get_llm_client
from .services.similarity import SimilarityService
from .services.form_service import FormService
from django.db import transaction
import json
from datetime import datetime
from .api_views import LearningOutcomeListCreateAPIView, LearningOutcomeRetrieveUpdateDestroyAPIView

# Grading imports
from grading.models import UploadSession, FileFormatConfig
from grading.services.parsing import ParsingService
from .services.analysis_service import ItemAnalysisService

class ItemPoolListView(LoginRequiredMixin, ListView):
    model = ItemPool
    template_name = 'itempool/pool_list.html'
    context_object_name = 'pools'
    
    def get_queryset(self):
        user = self.request.user
        if user.is_superuser or (hasattr(user, 'profile') and user.profile.role == 'ADMIN'):
            return ItemPool.objects.all().order_by('-created_at')
            
        # Sahibi olduğu veya yetkili olduğu havuzlar
        return ItemPool.objects.filter(
            Q(owner=user) | Q(permissions__user=user)
        ).distinct().select_related('owner').order_by('-created_at')


class ItemPoolCreateView(LoginRequiredMixin, CreateView):
    model = ItemPool
    form_class = ItemPoolForm
    template_name = 'itempool/pool_form.html'
    success_url = reverse_lazy('itempool:pool_list')

    def form_valid(self, form):
        form.instance.owner = self.request.user
        messages.success(self.request, 'Madde havuzu başarıyla oluşturuldu.')
        return super().form_valid(form)


class ItemPoolUpdateView(LoginRequiredMixin, UpdateView):
    model = ItemPool
    form_class = ItemPoolForm
    template_name = 'itempool/pool_form.html'
    
    def get_success_url(self):
        return reverse_lazy('itempool:pool_detail', kwargs={'pk': self.object.pk})

    def form_valid(self, form):
        messages.success(self.request, 'Madde havuzu güncellendi.')
        return super().form_valid(form)


class ItemPoolDetailView(PoolAccessMixin, DetailView):
    model = ItemPool
    template_name = 'itempool/pool_detail.html'
    context_object_name = 'pool'
    pool_permission_required = 'VIEWER'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Havuzdaki öğrenme çıktıları
        context['outcomes'] = self.object.outcomes.filter(is_active=True).order_by('order', 'code')
        
        # Havuzdaki maddeler (Pagination + Select Related)
        items_qs = self.object.item_instances.select_related('item').prefetch_related('learning_outcomes').all()
        
        paginator = Paginator(items_qs, 20)
        page_number = self.request.GET.get('page')
        context['items'] = paginator.get_page(page_number)
        
        # Havuzdaki blueprintler ve belirtke tabloları
        context['blueprints'] = self.object.blueprints.all().order_by('-created_at')
        context['spec_tables'] = self.object.spec_tables.all().order_by('-created_at')
        # Yeni çıktı eklemek için form
        context['outcome_form'] = LearningOutcomeForm()
        return context

@login_required
def add_learning_outcome(request, pool_id):
    pool = get_object_or_404(ItemPool, id=pool_id)
    if request.method == 'POST':
        form = LearningOutcomeForm(request.POST, pool=pool)
        if form.is_valid():
            outcome = form.save(commit=False)
            outcome.pool = pool
            outcome.save()
            if request.headers.get('HX-Request') == 'true':
                return render(request, 'itempool/partials/outcome_row.html', {'oc': outcome})
            messages.success(request, 'Öğrenme çıktısı eklendi.')
        else:
            if request.headers.get('HX-Request') == 'true':
                error_msg = ", ".join([f"{k}: {v[0]}" for k, v in form.errors.items()])
                resp = HttpResponse(
                    f'<div class="alert alert-danger alert-dismissible py-1 small mb-0 fade show">'
                    f'{error_msg}'
                    f'<button type="button" class="btn-close py-1" data-bs-dismiss="alert"></button></div>',
                    status=200
                )
                resp['HX-Retarget'] = '#outcome-add-error'
                resp['HX-Reswap'] = 'innerHTML'
                return resp
            messages.error(request, 'Form hatalı.')
    return redirect('itempool:pool_detail', pk=pool.id)

@login_required
def get_learning_outcome_row(request, pk):
    outcome = get_object_or_404(LearningOutcome, id=pk)
    return render(request, 'itempool/partials/outcome_row.html', {'oc': outcome})

@login_required
def edit_learning_outcome(request, pk):
    outcome = get_object_or_404(LearningOutcome, id=pk)
    if request.method == 'POST':
        form = LearningOutcomeForm(request.POST, instance=outcome, pool=outcome.pool)
        if form.is_valid():
            outcome = form.save()
            return render(request, 'itempool/partials/outcome_row.html', {'oc': outcome})
        else:
            if request.headers.get('HX-Request') == 'true':
                error_msg = ", ".join([f"{k}: {v[0]}" for k, v in form.errors.items()])
                return HttpResponse(f'<div class="alert alert-danger py-1 small mb-0">{error_msg}</div>', status=200)
            return render(request, 'itempool/partials/outcome_form_row.html', {'oc': outcome, 'form': form})
    else:
        form = LearningOutcomeForm(instance=outcome, pool=outcome.pool)
        return render(request, 'itempool/partials/outcome_form_row.html', {'oc': outcome, 'form': form})

@login_required
def delete_learning_outcome(request, pk):
    outcome = get_object_or_404(LearningOutcome, id=pk)
    if request.method == 'DELETE' or request.method == 'POST':
        outcome.delete()
        return HttpResponse("")
    return HttpResponse(status=400)

# Madde (Item) CRUD View'ları

@login_required
def item_create(request, pool_id):
    pool = get_object_or_404(ItemPool, id=pool_id)
    CHOICE_TYPES = ('MCQ', 'TF')

    if request.method == 'POST':
        form = ItemForm(request.POST)
        item_type = request.POST.get('item_type', 'MCQ')
        needs_choices = item_type in CHOICE_TYPES
        formset = ItemChoiceFormSet(request.POST) if needs_choices else None
        outcome_id = request.POST.get('learning_outcome')

        form_valid = form.is_valid()
        formset_valid = (not needs_choices) or (formset is not None and formset.is_valid())

        if form_valid and formset_valid:
            with transaction.atomic():
                item = form.save(commit=False)
                item.author = request.user
                item.save()

                if needs_choices and formset is not None:
                    formset.instance = item
                    formset.save()

                # Havuz ile ilişkilendir
                item_instance = ItemInstance.objects.create(
                    pool=pool,
                    item=item,
                    added_by=request.user
                )

                if outcome_id:
                    outcome = LearningOutcome.objects.filter(id=outcome_id, pool=pool).first()
                    if outcome:
                        item_instance.learning_outcomes.add(outcome)

                # Log kaydı
                ItemAuditLog.objects.create(
                    item=item,
                    action='CREATE',
                    user=request.user,
                    details_json={'pool_id': pool.id, 'outcome_id': outcome_id}
                )

                messages.success(request, 'Madde başarıyla oluşturuldu.')
                return redirect('itempool:pool_detail', pk=pool.id)
        else:
            if formset is None:
                formset = ItemChoiceFormSet()
    else:
        form = ItemForm()
        formset = ItemChoiceFormSet()

    outcomes = pool.outcomes.filter(is_active=True)
    return render(request, 'itempool/item_form.html', {
        'form': form,
        'formset': formset,
        'pool': pool,
        'outcomes': outcomes,
        'title': 'Yeni Madde Ekle'
    })

@login_required
def item_detail(request, pk):
    item_instance = get_object_or_404(ItemInstance, id=pk)
    analysis = item_instance.analysis_results.first()
    return render(request, 'itempool/item_detail.html', {
        'instance': item_instance,
        'analysis': analysis
    })

@login_required
def item_delete(request, pk):
    item_instance = get_object_or_404(ItemInstance, id=pk)
    pool_id = item_instance.pool.id
    # Gerçek Item'ı silmiyoruz, sadece instance'ı (havuzdaki halini) kaldırıyoruz (soft-delete benzeri mantık)
    # Eğer başka bir havuzda kullanılmıyorsa Item da silinebilir ama şimdilik sadece instance.
    # Log kaydı
    ItemAuditLog.objects.create(
        item=item_instance.item,
        action='REMOVE_FROM_POOL',
        user=request.user,
        details_json={'pool_id': pool_id}
    )
    
    item_instance.delete()
    messages.success(request, 'Madde havuzdan kaldırıldı.')
    return redirect('itempool:pool_detail', pk=pool_id)


# Docx Import View'ları

@login_required
def import_upload(request, pool_id):
    pool = get_object_or_404(ItemPool, id=pool_id)
    if request.method == 'POST' and request.FILES.get('docx_file'):
        uploaded_file = request.FILES['docx_file']
        batch = ImportBatch.objects.create(
            pool=pool,
            original_filename=uploaded_file.name,
            uploaded_file=uploaded_file,
            created_by=request.user
        )
        
        # Servis ile ayrıştır
        service = DocxImportService(batch.id)
        try:
            service.process()
            return redirect('itempool:import_preview', batch_id=batch.id)
        except Exception as e:
            batch.status = ImportBatch.Status.FAILED
            batch.save()
            messages.error(request, f'Dosya ayrıştırılırken hata oluştu: {str(e)}')
            
    return render(request, 'itempool/import_upload.html', {'pool': pool})

@login_required
def import_preview(request, batch_id):
    batch = get_object_or_404(ImportBatch, id=batch_id)
    draft_items = batch.draft_items.all()
    outcomes = batch.pool.outcomes.filter(is_active=True)
    return render(request, 'itempool/import_preview.html', {
        'batch': batch,
        'draft_items': draft_items,
        'outcomes': outcomes
    })

@login_required
@transaction.atomic
def import_commit(request, batch_id):
    batch = get_object_or_404(ImportBatch, id=batch_id)
    draft_items = batch.draft_items.filter(status=DraftItem.Status.PENDING)
    
    count = 0
    for draft in draft_items:
        # Form verilerini al
        is_active = request.POST.get(f'active_{draft.id}') == 'on'
        if not is_active:
            draft.status = DraftItem.Status.REJECTED
            draft.save()
            continue
            
        stem = request.POST.get(f'stem_{draft.id}', draft.stem)
        correct_answer = request.POST.get(f'correct_{draft.id}', draft.correct_answer)
        outcome_ids = request.POST.getlist(f'outcomes_{draft.id}')
        
        # Gerçek Item oluştur
        item = Item.objects.create(
            stem=stem,
            item_type=Item.ItemType.MULTIPLE_CHOICE,
            author=request.user,
            status=Item.Status.ACTIVE
        )
        
        # Şıkları oluştur
        for choice_data in draft.choices_json:
            is_correct = (choice_data['label'] == correct_answer)
            ItemChoice.objects.create(
                item=item,
                label=choice_data['label'],
                text=choice_data['text'],
                is_correct=is_correct
            )
        
        # Havuz ile ilişkilendir
        instance = ItemInstance.objects.create(
            pool=batch.pool,
            item=item,
            added_by=request.user
        )
        
        # Öğrenme çıktılarını ekle
        if outcome_ids:
            outcomes = LearningOutcome.objects.filter(id__in=outcome_ids)
            instance.learning_outcomes.set(outcomes)
        
        draft.status = DraftItem.Status.APPROVED
        draft.save()
        count += 1
        
    batch.status = ImportBatch.Status.COMPLETED
    batch.save()
    
    messages.success(request, f'{count} adet madde başarıyla havuza aktarıldı.')
    return redirect('itempool:pool_detail', pk=batch.pool.id)

import json
from .models import OutcomeSuggestion

@login_required
def item_suggest_outcomes(request, pk):
    item = get_object_or_404(Item, pk=pk)
    # Bu maddeyi içeren havuzun çıktılarını al
    # Birden fazla havuzda olabilir, ilkini veya aktif olanı baz alıyoruz
    instance = item.instances.first()
    if not instance:
        return HttpResponse("Madde hiçbir havuza dahil edilmemiş.")
    
    pool = instance.pool
    outcomes = pool.outcomes.filter(is_active=True)
    
    if not outcomes.exists():
        return HttpResponse("Bu havuzda henüz hiç öğrenme çıktısı tanımlanmamış.")
    
    client = get_llm_client()
    raw_response = client.suggest_outcomes(item.stem, outcomes)
    
    try:
        # JSON temizleme (bazı LLM'ler markdown code block içinde dönebiliyor)
        cleaned_json = raw_response.strip()
        if cleaned_json.startswith("```"):
            cleaned_json = cleaned_json.split("```")[1]
            if cleaned_json.startswith("json"):
                cleaned_json = cleaned_json[4:]
        
        data = json.loads(cleaned_json)
        outcome_id = data.get('outcome_id')
        score = data.get('score', 0)
        reason = data.get('reason', '')
        
        if outcome_id:
            learning_outcome = LearningOutcome.objects.get(id=outcome_id)
            # Mevcut önerileri temizle veya yeni ekle
            OutcomeSuggestion.objects.filter(item=item).delete()
            suggestion = OutcomeSuggestion.objects.create(
                item=item,
                learning_outcome=learning_outcome,
                score=score,
                reasoning=reason
            )
            return render(request, 'itempool/partials/outcome_suggestions.html', {
                'item': item,
                'suggestion': suggestion,
                'instance': instance
            })
    except Exception as e:
        return HttpResponse(f"Öneri ayrıştırılamadı: {str(e)}")

    return HttpResponse("Öneri alınamadı.")

@login_required
def pool_bulk_suggest_outcomes(request, pk):
    pool = get_object_or_404(ItemPool, pk=pk)
    # Öğrenme çıktısı atanmamış instance'lar
    instances = pool.item_instances.filter(learning_outcomes__isnull=True).distinct()
    
    if not instances.exists():
        messages.info(request, "Tüm maddelere zaten öğrenme çıktısı atanmış.")
        return redirect('itempool:pool_detail', pk=pk)
        
    outcomes = list(pool.outcomes.filter(is_active=True))
    if not outcomes:
        messages.error(request, "Havuzda tanımlı aktif öğrenme çıktısı bulunamadı.")
        return redirect('itempool:pool_detail', pk=pk)
        
    client = get_llm_client()
    count = 0
    
    for inst in instances:
        item = inst.item
        raw_response = client.suggest_outcomes(item.stem, outcomes)
        try:
            cleaned_json = raw_response.strip()
            if cleaned_json.startswith("```"):
                cleaned_json = cleaned_json.split("```")[1]
                if cleaned_json.startswith("json"):
                    cleaned_json = cleaned_json[4:]
            
            data = json.loads(cleaned_json)
            outcome_id = data.get('outcome_id')
            if outcome_id:
                learning_outcome = LearningOutcome.objects.get(id=outcome_id)
                OutcomeSuggestion.objects.update_or_create(
                    item=item,
                    learning_outcome=learning_outcome,
                    defaults={
                        'score': data.get('score', 0),
                        'reasoning': data.get('reason', '')
                    }
                )
                count += 1
        except:
            continue
            
    messages.success(request, f"{count} madde için AI önerileri hazırlandı.")
    return redirect('itempool:pool_detail', pk=pk)

@login_required
def item_assign_outcome(request, pk, outcome_id):
    item = get_object_or_404(Item, pk=pk)
    outcome = get_object_or_404(LearningOutcome, pk=outcome_id)
    
    # Tüm instance'lar için güncelle (M2M ekle)
    for instance in item.instances.all():
        instance.learning_outcomes.add(outcome)
    
    # Öneriyi kabul et
    OutcomeSuggestion.objects.filter(item=item, learning_outcome=outcome).update(status=OutcomeSuggestion.Status.ACCEPTED)
    
    messages.success(request, f'Madde {outcome.code} çıktısına başarıyla eşlendi.')
    return redirect('itempool:item_detail', pk=pk)

@login_required
@transaction.atomic
def item_generate_ai(request, pk):
    outcome = get_object_or_404(LearningOutcome, id=pk)
    
    if request.method == 'POST':
        difficulty = request.POST.get('difficulty', 'Orta')
        item_type = request.POST.get('item_type', 'MCQ')
        count = int(request.POST.get('count', 1))
        
        client = get_llm_client()
        raw_response = client.generate_item(
            outcome_text=outcome.description,
            bloom_level=outcome.get_level_display(),
            difficulty=difficulty,
            count=count,
            item_type=item_type
        )
        
        try:
            # JSON temizleme
            cleaned_json = raw_response.strip()
            if cleaned_json.startswith("```"):
                chunks = cleaned_json.split("```")
                if len(chunks) > 1:
                    cleaned_json = chunks[1]
                    if cleaned_json.startswith("json"):
                        cleaned_json = cleaned_json[4:]
            
            data_list = json.loads(cleaned_json)
            if not isinstance(data_list, list):
                data_list = [data_list]
            
            # ImportBatch oluştur (AI-[Tarih] formatında)
            now_str = datetime.now().strftime("%d.%m.%Y %H:%M")
            batch = ImportBatch.objects.create(
                pool=outcome.pool,
                original_filename=f"AI-{now_str}",
                created_by=request.user,
                status=ImportBatch.Status.PENDING
            )
            
            for data in data_list:
                # DraftItem oluştur
                draft = DraftItem.objects.create(
                    batch=batch,
                    stem=data.get('stem'),
                    choices_json=data.get('choices'),
                    correct_answer=data.get('correct_answer'),
                    status=DraftItem.Status.PENDING
                )
                draft.learning_outcomes.add(outcome)
            
            messages.success(request, f'AI tarafından {len(data_list)} yeni soru taslağı oluşturuldu.')
            return redirect('itempool:import_preview', batch_id=batch.id)
            
        except Exception as e:
            messages.error(request, f'AI soru üretirken hata oluştu: {str(e)}')
            return redirect('itempool:pool_detail', pk=outcome.pool.id)
            
    return HttpResponse(status=405)

@login_required
def item_check_duplicate(request):
    stem = request.GET.get('stem', '')
    pool_id = request.GET.get('pool_id')
    try:
        threshold_val = float(request.GET.get('threshold', 85))
    except ValueError:
        threshold_val = 85
        
    threshold = threshold_val / 100.0
    
    if not stem or len(stem) < 20:
        return HttpResponse('')
        
    similar_items = SimilarityService.find_similar_items(
        query_text=stem, 
        pool_id=pool_id, 
        threshold=threshold
    )
    
    if not similar_items:
        return HttpResponse('')
        
    if not similar_items:
        return HttpResponse('')
        
    return render(request, 'itempool/partials/duplicate_warning.html', {
        'similar_items': similar_items,
        'threshold_percent': int(threshold_val)
    })

@login_required
def pool_semantic_search(request, pool_id):
    pool = get_object_or_404(ItemPool, id=pool_id)
    query = request.GET.get('q', '')
    
    if not query:
        return HttpResponse("")
        
    # Aramada eşik değerini daha düşük tutarak geniş sonuç veriyoruz
    results = SimilarityService.find_similar_items(
        query_text=query,
        pool_id=pool.id,
        threshold=0.5, 
        top_n=10
    )
    
    return render(request, 'itempool/partials/semantic_search_results.html', {
        'results': results,
        'query': query,
        'pool': pool
    })

@login_required
def pool_vectorize_confirm(request, pool_id):
    pool = get_object_or_404(ItemPool, id=pool_id)
    
    # Henüz vektörize edilmemiş maddeler
    items_to_vectorize = Item.objects.filter(
        instances__pool=pool, 
        embedding__isnull=True
    ).distinct()
    
    count = items_to_vectorize.count()
    if count == 0:
        return HttpResponse('''
            <div class="alert alert-info py-2 small mb-0">
                <i class="bi bi-check-circle"></i> Tüm maddeler zaten vektörize edilmiş.
            </div>
        ''')
        
    text_list = [SimilarityService.get_item_text(item) for item in items_to_vectorize]
    cost_info = SimilarityService.calculate_embedding_cost(text_list)
    
    return render(request, 'itempool/partials/vectorize_confirm.html', {
        'pool': pool,
        'count': count,
        'cost_info': cost_info
    })

@login_required
def pool_vectorize_start(request, pool_id):
    pool = get_object_or_404(ItemPool, id=pool_id)
    
    if request.method != 'POST':
        return HttpResponseForbidden()
        
    items_to_vectorize = Item.objects.filter(
        instances__pool=pool, 
        embedding__isnull=True
    ).distinct()
    
    client = get_llm_client()
    count = 0
    import time
    for item in items_to_vectorize:
        text = SimilarityService.get_item_text(item)
        vector = client.get_embedding(text)
        if vector:
            ItemEmbedding.objects.update_or_create(item=item, defaults={'vector': vector})
            count += 1
            # Basit rate limit
            time.sleep(0.3)
            
    return HttpResponse(f'''
        <div class="alert alert-success py-2 small mb-0">
            <i class="bi bi-check-all"></i> {count} adet madde başarıyla vektörize edildi.
        </div>
        <script>setTimeout(() => window.location.reload(), 2000);</script>
    ''')

@login_required
def item_suggest_distractors(request):
    stem = request.GET.get('stem', '')
    correct_answer = request.GET.get('correct_answer', '')
    
    if not stem or len(stem) < 10:
        return HttpResponse('<div class="alert alert-warning py-1 small mb-0">Önce geçerli bir madde kökü yazmalısınız.</div>')
    
    client = get_llm_client()
    raw_response = client.suggest_distractors(stem, correct_answer)
    
    try:
        # JSON temizleme
        cleaned_json = raw_response.strip()
        if cleaned_json.startswith("```"):
            chunks = cleaned_json.split("```")
            if len(chunks) > 1:
                cleaned_json = chunks[1]
                if cleaned_json.startswith("json"):
                    cleaned_json = cleaned_json[4:]
        
        distractors = json.loads(cleaned_json)
        if not isinstance(distractors, list):
            distractors = [str(distractors)]
            
        return render(request, 'itempool/partials/distractor_suggestions.html', {'distractors': distractors})
    except Exception as e:
        return HttpResponse(f'<div class="alert alert-danger py-1 small mb-0">Hata: {str(e)}</div>')

@login_required
@transaction.atomic
def item_clone_variation(request, pk):
    item_instance = get_object_or_404(ItemInstance, id=pk)
    item = item_instance.item
    
    choices = []
    if item.item_type in ['MCQ', 'TF']:
        choices = [{"label": c.label, "text": c.text, "is_correct": c.is_correct} for c in item.choices.all()]
    
    client = get_llm_client()
    raw_response = client.generate_variation(item.stem, json.dumps(choices))
    
    try:
        # JSON temizleme
        cleaned_json = raw_response.strip()
        if cleaned_json.startswith("```"):
            chunks = cleaned_json.split("```")
            if len(chunks) > 1:
                cleaned_json = chunks[1]
                if cleaned_json.startswith("json"):
                    cleaned_json = cleaned_json[4:]
        
        data = json.loads(cleaned_json)
        
        # ImportBatch oluştur
        now_str = datetime.now().strftime("%d.%m.%Y %H:%M")
        batch = ImportBatch.objects.create(
            pool=item_instance.pool,
            original_filename=f"AI-Variation-{now_str}",
            created_by=request.user,
            status=ImportBatch.Status.PENDING
        )
        
        # DraftItem oluştur
        draft = DraftItem.objects.create(
            batch=batch,
            stem=data.get('stem', 'Soru kökü alınamadı'),
            choices_json=data.get('choices', []),
            correct_answer=data.get('correct_answer'),
            status=DraftItem.Status.PENDING
        )
        # Mevcut kazanımları kopyala
        for outcome in item_instance.learning_outcomes.all():
            draft.learning_outcomes.add(outcome)
            
        messages.success(request, 'AI tarafından sorunun bir varyasyonu oluşturuldu. Önizleyip onaylayabilirsiniz.')
        return redirect('itempool:import_preview', batch_id=batch.id)
        
    except Exception as e:
        messages.error(request, f'Varyasyon üretilirken hata oluştu: {str(e)}')
        return redirect('itempool:item_detail', pk=pk)

@login_required
def item_suggest_improvements(request, pk):
    instance = get_object_or_404(ItemInstance, id=pk)
    item = instance.item
    
    choices = []
    if item.item_type in ['MCQ', 'TF']:
        choices = [{"label": c.label, "text": c.text} for c in item.choices.all()]
    
    client = get_llm_client()
    raw_response = client.suggest_improvements(item.stem, json.dumps(choices))
    
    try:
        # JSON temizleme
        cleaned_json = raw_response.strip()
        if cleaned_json.startswith("```"):
            chunks = cleaned_json.split("```")
            if len(chunks) > 1:
                cleaned_json = chunks[1]
                if cleaned_json.startswith("json"):
                    cleaned_json = cleaned_json[4:]
        
        data = json.loads(cleaned_json)
        return render(request, 'itempool/partials/item_improvements.html', {
            'instance': instance, 
            'improved': data
        })
    except Exception as e:
        return HttpResponse(f'<div class="alert alert-danger py-1 small mb-0">Hata: {str(e)}</div>')

@login_required
def item_detail_edit(request, pk, section):
    instance = get_object_or_404(ItemInstance, id=pk)
    item = instance.item
    
    if section == 'stem':
        form = ItemDetailEditForm(instance=item)
        return render(request, 'itempool/partials/item_detail_edit_form.html', {
            'instance': instance, 'form': form, 'section': section
        })
    elif section == 'meta':
        form = ItemDetailEditForm(instance=item)
        return render(request, 'itempool/partials/item_detail_edit_form.html', {
            'instance': instance, 'form': form, 'section': section
        })
    elif section == 'outcomes':
        outcomes = instance.pool.outcomes.filter(is_active=True)
        return render(request, 'itempool/partials/item_detail_edit_form.html', {
            'instance': instance, 'outcomes': outcomes, 'section': section
        })
    
    return HttpResponse(status=400)

@login_required
def item_detail_save(request, pk, section):
    instance = get_object_or_404(ItemInstance, id=pk)
    item = instance.item
    
    if request.method == 'POST':
        if section in ['stem', 'meta']:
            form = ItemDetailEditForm(request.POST, instance=item)
            if form.is_valid():
                form.save()
                return render(request, 'itempool/partials/item_detail_card.html', {
                    'instance': instance, 'section': section
                })
        elif section == 'outcomes':
            outcome_ids = request.POST.getlist('outcomes')
            outcomes = LearningOutcome.objects.filter(id__in=outcome_ids)
            instance.learning_outcomes.set(outcomes)
            return render(request, 'itempool/partials/item_detail_card.html', {
                'instance': instance, 'section': section
            })
            
    return HttpResponse(status=400)


# Test Formu View'ları (Faz 5)

@login_required
def test_form_create(request):
    # İsteğe bağlı: havuz önceden seçilmişse URL query param'dan al
    pool_id = request.GET.get('pool_id') or request.POST.get('pool_id')
    pool = None
    if pool_id:
        pool = ItemPool.objects.filter(id=pool_id).first()

    if request.method == 'POST':
        form = TestFormForm(request.POST)
        if form.is_valid():
            test_form = form.save(commit=False)
            test_form.created_by = request.user
            # Hangi havuzdan başlatıldığı bilgisini metadata'ya kaydet
            if pool:
                test_form.generation_metadata = {'source_pool_id': pool.id}
            test_form.save()

            method = form.cleaned_data['creation_method']
            if method == 'MANUAL':
                return redirect('itempool:test_form_edit_items', pk=test_form.id)
            elif method == 'BLUEPRINT':
                return redirect('itempool:test_form_wizard_blueprint', pk=test_form.id)
            return redirect('itempool:test_form_edit_items', pk=test_form.id)
    else:
        form = TestFormForm()

    return render(request, 'itempool/test_form_form.html', {
        'pool': pool,
        'form': form
    })

@login_required
def test_form_detail(request, pk):
    test_form = get_object_or_404(TestForm, id=pk)
    items = test_form.form_items.all().select_related('item_instance__item')
    
    # Basit istatistik hesaplama
    total_points = sum(item.points for item in items)
    item_count = items.count()
    
    exam_templates = ExamTemplate.objects.order_by('-is_default', 'name')
    distribution = FormService.get_choice_distribution(test_form)

    return render(request, 'itempool/test_form_detail.html', {
        'form': test_form,
        'items': items,
        'total_points': total_points,
        'item_count': item_count,
        'exam_templates': exam_templates,
        'distribution': distribution,
    })

@login_required
def test_form_edit_items(request, pk):
    test_form = get_object_or_404(TestForm, id=pk)

    # Havuzu metadata'dan veya query param'dan al
    pool_id = request.GET.get('pool_id') or test_form.generation_metadata.get('source_pool_id')
    pool = None
    if pool_id:
        pool = ItemPool.objects.filter(id=pool_id).first()

    form_item_ids = test_form.form_items.values_list('item_instance_id', flat=True)
    if pool:
        available_items = pool.item_instances.exclude(id__in=form_item_ids)
    else:
        # Kullanıcının erişebildiği tüm havuzlardan maddeler
        from django.db.models import Q
        accessible_pool_ids = ItemPool.objects.filter(
            Q(owner=request.user) | Q(permissions__user=request.user)
        ).values_list('id', flat=True)
        available_items = ItemInstance.objects.filter(
            pool_id__in=accessible_pool_ids
        ).exclude(id__in=form_item_ids).select_related('item', 'pool')

    # Havuz seçimi için tüm erişilebilir havuzlar
    from django.db.models import Q as Q2
    pools = ItemPool.objects.filter(
        Q2(owner=request.user) | Q2(permissions__user=request.user)
    ).distinct()

    return render(request, 'itempool/test_form_edit_items.html', {
        'form': test_form,
        'available_items': available_items,
        'current_items': test_form.form_items.all(),
        'pool': pool,
        'pools': pools,
    })

@login_required
def test_form_add_item(request, pk, instance_id):
    test_form = get_object_or_404(TestForm, id=pk)
    instance = get_object_or_404(ItemInstance, id=instance_id)
    
    # Zaten ekli mi?
    if not FormItem.objects.filter(form=test_form, item_instance=instance).exists():
        order = test_form.form_items.count() + 1
        FormItem.objects.create(form=test_form, item_instance=instance, order=order)
    
    if request.headers.get('HX-Request') == 'true':
        return render(request, 'itempool/partials/test_form_items_list.html', {
            'form': test_form,
            'current_items': test_form.form_items.all().order_by('order')
        })
    return redirect('itempool:test_form_edit_items', pk=pk)

@login_required
def test_form_remove_item(request, pk, item_id):
    test_form = get_object_or_404(TestForm, id=pk)
    form_item = get_object_or_404(FormItem, id=item_id, form=test_form)
    
    form_item.delete()
    
    # Sıralamayı güncelle
    for i, item in enumerate(test_form.form_items.all().order_by('order'), 1):
        item.order = i
        item.save()

    if request.headers.get('HX-Request') == 'true':
        return render(request, 'itempool/partials/test_form_items_list.html', {
            'form': test_form,
            'current_items': test_form.form_items.all().order_by('order')
        })
    return redirect('itempool:test_form_edit_items', pk=pk)


@login_required
def test_form_wizard_blueprint(request, pk):
    test_form = get_object_or_404(TestForm, id=pk)
    pool_id = test_form.generation_metadata.get('source_pool_id')
    pool = get_object_or_404(ItemPool, id=pool_id) if pool_id else None
    if not pool:
        messages.error(request, 'Blueprint oluşturmak için bir havuz kaynağı bulunamadı.')
        return redirect('itempool:test_form_edit_items', pk=pk)
    outcomes = pool.outcomes.filter(is_active=True).order_by('order')
    
    if request.method == 'POST':
        total_items = int(request.POST.get('total_items', 0))
        distribution = {}
        for oc in outcomes:
            count = int(request.POST.get(f'oc_{oc.id}', 0))
            if count > 0:
                distribution[str(oc.id)] = count
        
        # Blueprint kaydet
        blueprint = Blueprint.objects.create(
            name=f"{test_form.name} Şablonu",
            pool=pool,
            distribution_json=distribution,
            total_items=total_items,
            created_by=request.user
        )
        
        # Soruları otomatik seç ve ekle
        _generate_items_from_blueprint(test_form, blueprint)
        
        return redirect('itempool:test_form_detail', pk=test_form.id)
        
    return render(request, 'itempool/test_form_wizard_blueprint.html', {
        'form': test_form,
        'outcomes': outcomes
    })

def _generate_items_from_blueprint(test_form, blueprint):
    """Blueprint'e göre test formuna madde ekler."""
    with transaction.atomic():
        # Mevcut maddeleri temizle (eğer varsa)
        test_form.form_items.all().delete()
        
        current_order = 1
        used_ids = set()  # Aynı maddenin tekrar eklenmesini önle
        distribution = blueprint.distribution_json
        for oc_id, count in distribution.items():
            items = ItemInstance.objects.filter(
                pool=blueprint.pool, 
                learning_outcomes__id=oc_id
            ).exclude(id__in=used_ids).order_by('?')[:count]
            
            for inst in items:
                FormItem.objects.create(
                    form=test_form,
                    item_instance=inst,
                    order=current_order
                )
                used_ids.add(inst.id)
                current_order += 1

@login_required
def blueprint_clone(request, pk):
    blueprint = get_object_or_404(Blueprint, pk=pk)
    
    # Yeni bir TestForm oluştur ve bu blueprint'i kullan
    new_form_name = f"{blueprint.name} - Klon"
    new_form = TestForm.objects.create(
        name=new_form_name,
        created_by=request.user,
        generation_metadata={'cloned_from_blueprint': blueprint.id, 'source_pool_id': blueprint.pool.id}
    )
    
    _generate_items_from_blueprint(new_form, blueprint)
    
    messages.success(request, f'Blueprint kullanılarak "{new_form_name}" oluşturuldu.')
    return redirect('itempool:test_form_detail', pk=new_form.id)

@login_required
def analysis_upload(request):
    pools = ItemPool.objects.all()
    formats = FileFormatConfig.objects.filter(is_active=True)
    
    if request.method == 'POST':
        pool_id = request.POST.get('pool_id')
        form_id = request.POST.get('form_id')
        format_id = request.POST.get('file_format')
        data_file = request.FILES.get('data_file')
        
        if not all([pool_id, format_id, data_file]):
            messages.error(request, "Lütfen gerekli tüm alanları doldurun.")
            return redirect('itempool:analysis_upload')
            
        pool = get_object_or_404(ItemPool, id=pool_id)
        file_format = get_object_or_404(FileFormatConfig, id=format_id)
        test_form = get_object_or_404(TestForm, id=form_id) if form_id else None
        
        # 1. UploadSession oluştur
        session = UploadSession.objects.create(
            owner=request.user,
            original_filename=data_file.name,
            uploaded_file=data_file,
            file_format=file_format,
            points_per_question=request.POST.get('points_per_question', 1.0),
            wrong_to_correct_ratio=request.POST.get('wrong_to_correct_ratio', 0)
        )
        
        # 2. Ayrıştır ve notla (NefOptik servisi)
        parser = ParsingService()
        success = parser.process_upload(session)
        
        if success:
            # 3. Madde Analizi Yap (MaddeHavuzu servisi)
            analysis_service = ItemAnalysisService()
            
            # Eşleştirme Sözlüğü Hazırla
            # Eğer form seçildiyse formdaki sorularla eşleştir
            item_mapping = {}
            if test_form:
                for fitem in test_form.form_items.all().order_by('order'):
                    # Optik veride soru sırası 0-tabanlıdır, FormItem.order 1-tabanlıdır
                    item_mapping[fitem.order - 1] = fitem.item_instance_id
            
            # Analizi çalıştır
            processed_count = analysis_service.process_session_results(
                session, item_mapping, test_form=test_form
            )
            
            messages.success(request, f"Veri başarıyla işlendi ve {processed_count} madde analizi kaydedildi.")
            return redirect('itempool:pool_detail', pk=pool.id)
        else:
            messages.error(request, f"Dosya işlenirken hata oluştu: {session.error_summary}")
            
    return render(request, 'itempool/analysis_upload.html', {
        'pools': pools,
        'formats': formats
    })

@login_required
def analysis_get_forms(request):
    pool_id = request.GET.get('pool_id')
    if not pool_id:
        return HttpResponse('<option value="">Önce havuz seçin...</option>')

    # Pool bilgisi artık TestForm'da FK olarak değil, tüm formlar döndürülür
    forms = TestForm.objects.filter(created_by=request.user).order_by('-created_at')
    return render(request, 'itempool/partials/analysis_form_options.html', {'forms': forms})


# ============================================================
# Ders (Course) View'ları
# ============================================================

@login_required
def course_list(request):
    courses = Course.objects.filter(created_by=request.user).prefetch_related('pools').order_by('-created_at')
    return render(request, 'itempool/course_list.html', {'courses': courses})


@login_required
def course_create(request):
    if request.method == 'POST':
        form = CourseForm(request.POST)
        if form.is_valid():
            course = form.save(commit=False)
            course.created_by = request.user
            course.save()
            form.save_m2m()  # pools M2M kaydet
            messages.success(request, f'"{course}" dersi oluşturuldu.')
            return redirect('itempool:course_detail', pk=course.pk)
    else:
        form = CourseForm()
    return render(request, 'itempool/course_form.html', {'form': form, 'title': 'Yeni Ders'})


@login_required
def course_update(request, pk):
    course = get_object_or_404(Course, pk=pk, created_by=request.user)
    if request.method == 'POST':
        form = CourseForm(request.POST, instance=course)
        if form.is_valid():
            form.save()
            messages.success(request, 'Ders güncellendi.')
            return redirect('itempool:course_detail', pk=course.pk)
    else:
        form = CourseForm(instance=course)
    return render(request, 'itempool/course_form.html', {'form': form, 'course': course, 'title': 'Dersi Düzenle'})


@login_required
def course_detail(request, pk):
    from datetime import date
    course = get_object_or_404(Course, pk=pk, created_by=request.user)
    test_forms = course.test_forms.prefetch_related('form_items').order_by('-created_at')
    spec_tables = course.spec_tables.all().order_by('-created_at')
    applications = course.exam_applications.select_related('test_form').order_by('-applied_at')
    applications_by_form = {app.test_form_id: app for app in applications}
    tf_with_app = [(tf, applications_by_form.get(tf.pk)) for tf in test_forms]
    return render(request, 'itempool/course_detail.html', {
        'course': course,
        'test_forms': test_forms,
        'tf_with_app': tf_with_app,
        'spec_tables': spec_tables,
        'applications': applications,
        'today': date.today().isoformat(),
    })


# ── Belirtke Tablosu ─────────────────────────────────────────

@login_required
def course_spec_table_create(request, course_pk):
    course = get_object_or_404(Course, pk=course_pk, created_by=request.user)
    outcomes = LearningOutcome.objects.filter(
        pool__in=course.pools.all(), is_active=True
    ).select_related('pool').order_by('pool', 'order', 'code')

    if request.method == 'POST':
        form = CourseSpecTableForm(request.POST)
        if form.is_valid():
            spec = form.save(commit=False)
            spec.course = course
            spec.created_by = request.user
            # rows_json form POST'undan manuel parse et
            rows = []
            topic_count = int(request.POST.get('topic_count', 0))
            total = 0
            for i in range(topic_count):
                topic = request.POST.get(f'topic_{i}', '').strip()
                if not topic:
                    continue
                row_outcomes = []
                for oc in outcomes:
                    count = int(request.POST.get(f'count_{i}_{oc.id}', 0) or 0)
                    if count > 0:
                        row_outcomes.append({
                            'outcome_id': oc.id,
                            'outcome_code': oc.code,
                            'bloom_level': oc.level,
                            'question_count': count,
                        })
                        total += count
                if row_outcomes:
                    rows.append({'topic': topic, 'outcomes': row_outcomes})
            spec.rows_json = rows
            spec.total_questions = total
            spec.save()
            messages.success(request, 'Belirtke tablosu kaydedildi.')
            return redirect('itempool:course_detail', pk=course.pk)
    else:
        form = CourseSpecTableForm()
    return render(request, 'itempool/course_spec_table_form.html', {
        'form': form,
        'course': course,
        'outcomes': outcomes,
    })


@login_required
def course_spec_table_delete(request, pk):
    spec = get_object_or_404(CourseSpecTable, pk=pk, course__created_by=request.user)
    course_pk = spec.course_id
    if request.method == 'POST':
        spec.delete()
        messages.success(request, 'Belirtke tablosu silindi.')
    return redirect('itempool:course_detail', pk=course_pk)


# ── Derse Ait Sınav Formu Oluşturma ──────────────────────────

@login_required
def course_test_form_create(request, course_pk):
    """Derse ait yeni sınav formu oluşturur."""
    course = get_object_or_404(Course, pk=course_pk, created_by=request.user)

    if request.method == 'POST':
        form = TestFormCreateForm(request.POST, course=course)
        if form.is_valid():
            tf = form.save(commit=False)
            tf.course = course
            tf.created_by = request.user

            # Otomatik seçim kriterlerini metadata olarak sakla
            method = request.POST.get('method', 'MANUAL')
            excluded_ids = [int(x) for x in request.POST.getlist('excluded_forms')]
            metadata = {
                'method': method,
                'difficulty': form.cleaned_data.get('difficulty', 'MIXED'),
                'item_type_counts': {
                    'MCQ': form.cleaned_data.get('n_mcq') or 0,
                    'TF': form.cleaned_data.get('n_tf') or 0,
                    'SHORT_ANSWER': form.cleaned_data.get('n_short') or 0,
                    'OPEN': form.cleaned_data.get('n_open') or 0,
                },
                'excluded_form_ids': excluded_ids,
            }
            tf.generation_metadata = metadata
            tf.save()
            form.save_m2m()  # pools M2M

            if method == 'AUTO':
                _auto_select_items(tf, course)
                messages.success(request, f'Sınav formu otomatik oluşturuldu: {tf.form_items.count()} soru seçildi.')
                return redirect('itempool:test_form_detail', pk=tf.pk)
            else:
                return redirect('itempool:test_form_edit_items', pk=tf.pk)
    else:
        form = TestFormCreateForm(course=course)

    existing_forms = course.test_forms.order_by('-created_at')
    return render(request, 'itempool/course_test_form_create.html', {
        'form': form,
        'course': course,
        'existing_forms': existing_forms,
    })


def _auto_select_items(test_form, course):
    """
    generation_metadata'ya göre havuzlardan otomatik madde seçer.
    Zorluk, madde türü ve dışlama kriterlerini uygular.
    """
    import random
    meta = test_form.generation_metadata
    difficulty = meta.get('difficulty', 'MIXED')
    type_counts = meta.get('item_type_counts', {})
    excluded_form_ids = meta.get('excluded_form_ids', [])

    # Dışlanan sınavlardaki maddelerin ID'leri
    excluded_instance_ids = set(
        FormItem.objects.filter(form_id__in=excluded_form_ids)
        .values_list('item_instance_id', flat=True)
    )

    # Bu derse daha önce uygulanan maddeler de dışlanabilir (isteğe bağlı)
    pool_ids = list(test_form.pools.values_list('id', flat=True))
    if not pool_ids:
        pool_ids = list(course.pools.values_list('id', flat=True))

    # Zorluk filtresi
    difficulty_map = {
        'EASY': ['EASY'],
        'MEDIUM': ['MEDIUM'],
        'HARD': ['HARD'],
        'MIXED': ['EASY', 'MEDIUM', 'HARD'],
    }
    allowed_difficulties = difficulty_map.get(difficulty, ['EASY', 'MEDIUM', 'HARD'])

    order = 1
    test_form.form_items.all().delete()

    for itype, count in type_counts.items():
        if count <= 0:
            continue
        qs = list(
            ItemInstance.objects.filter(
                pool_id__in=pool_ids,
                item__item_type=itype,
                item__difficulty_intended__in=allowed_difficulties,
            ).exclude(
                id__in=excluded_instance_ids
            ).select_related('item')
        )
        random.shuffle(qs)
        for inst in qs[:count]:
            FormItem.objects.create(form=test_form, item_instance=inst, order=order)
            order += 1


@login_required
def exam_application_create(request, course_pk=None):
    initial = {}
    course = None
    if course_pk:
        course = get_object_or_404(Course, pk=course_pk, created_by=request.user)
        initial['course'] = course

    if request.method == 'POST':
        form = ExamApplicationForm(request.POST)
        if form.is_valid():
            app = form.save(commit=False)
            app.created_by = request.user
            app.save()
            messages.success(request, 'Sınav uygulaması kaydedildi.')
            return redirect('itempool:course_detail', pk=app.course.pk)
    else:
        form = ExamApplicationForm(initial=initial)
    return render(request, 'itempool/exam_application_form.html', {
        'form': form,
        'course': course,
        'title': 'Sınav Uygulaması Kaydet'
    })


@login_required
def exam_application_quick(request, course_pk, tf_pk):
    """Inline 'mark as applied' from the course detail page — no separate form page needed."""
    from datetime import date as date_cls
    course = get_object_or_404(Course, pk=course_pk, created_by=request.user)
    tf = get_object_or_404(TestForm, pk=tf_pk)
    if request.method == 'POST':
        applied_at_str = request.POST.get('applied_at') or str(date_cls.today())
        notes = request.POST.get('notes', '')
        try:
            applied_at = date_cls.fromisoformat(applied_at_str)
        except (ValueError, TypeError):
            applied_at = date_cls.today()
        app, created = ExamApplication.objects.get_or_create(
            test_form=tf, course=course,
            defaults={'applied_at': applied_at, 'notes': notes, 'created_by': request.user},
        )
        if created:
            messages.success(request, f'"{tf.name}" uygulandı olarak işaretlendi.')
        else:
            messages.info(request, 'Bu sınav formu zaten uygulandı olarak kaydedilmiş.')
    return redirect('itempool:course_detail', pk=course_pk)


@login_required
def exam_application_delete(request, pk):
    app = get_object_or_404(ExamApplication, pk=pk, created_by=request.user)
    course_pk = app.course_id
    if request.method == 'POST':
        app.delete()
        messages.success(request, 'Sınav uygulaması silindi.')
    return redirect('itempool:course_detail', pk=course_pk)


@login_required
def course_applied_items(request, course_pk):
    """Bir derse daha önce uygulanan madde instance ID'lerini JSON döndürür."""
    from django.http import JsonResponse
    course = get_object_or_404(Course, pk=course_pk, created_by=request.user)
    applied_ids = list(course.get_applied_item_instance_ids())
    return JsonResponse({'applied_item_instance_ids': applied_ids, 'count': len(applied_ids)})


# ============================================================
# Faz 12 — Sınav Kağıdı Şablonları ve PDF Oluşturma
# ============================================================

@login_required
def exam_template_list(request):
    templates = ExamTemplate.objects.order_by('-is_default', 'name')
    return render(request, 'itempool/exam_template_list.html', {'templates': templates})


@login_required
def exam_template_create(request):
    from .forms import ExamTemplateForm
    if request.method == 'POST':
        form = ExamTemplateForm(request.POST, request.FILES)
        if form.is_valid():
            tpl = form.save(commit=False)
            tpl.created_by = request.user

            # GrapesJS verilerini hidden inputlardan al
            tpl.header_html = request.POST.get('header_html', '') or ''
            tpl.header_css = request.POST.get('header_css', '') or ''
            tpl.footer_html = request.POST.get('footer_html', '') or ''
            tpl.footer_css = request.POST.get('footer_css', '') or ''

            header_json = request.POST.get('header_design_json', '')
            footer_json = request.POST.get('footer_design_json', '')
            if header_json:
                import json
                try:
                    tpl.header_design_json = json.loads(header_json)
                except (json.JSONDecodeError, TypeError):
                    tpl.header_design_json = None
            if footer_json:
                import json
                try:
                    tpl.footer_design_json = json.loads(footer_json)
                except (json.JSONDecodeError, TypeError):
                    tpl.footer_design_json = None

            tpl.save()
            messages.success(request, 'Şablon oluşturuldu.')
            return redirect('itempool:exam_template_list')
    else:
        form = ExamTemplateForm()
    return render(request, 'itempool/exam_template_form.html', {'form': form, 'title': 'Yeni Şablon'})


@login_required
def exam_template_update(request, pk):
    from .forms import ExamTemplateForm
    tpl = get_object_or_404(ExamTemplate, pk=pk)
    if request.method == 'POST':
        form = ExamTemplateForm(request.POST, request.FILES, instance=tpl)
        if form.is_valid():
            tpl = form.save(commit=False)

            # GrapesJS verilerini hidden inputlardan al
            tpl.header_html = request.POST.get('header_html', '') or ''
            tpl.header_css = request.POST.get('header_css', '') or ''
            tpl.footer_html = request.POST.get('footer_html', '') or ''
            tpl.footer_css = request.POST.get('footer_css', '') or ''

            header_json = request.POST.get('header_design_json', '')
            footer_json = request.POST.get('footer_design_json', '')
            if header_json:
                import json
                try:
                    tpl.header_design_json = json.loads(header_json)
                except (json.JSONDecodeError, TypeError):
                    pass
            else:
                tpl.header_design_json = None
            if footer_json:
                import json
                try:
                    tpl.footer_design_json = json.loads(footer_json)
                except (json.JSONDecodeError, TypeError):
                    pass
            else:
                tpl.footer_design_json = None

            tpl.save()
            messages.success(request, 'Şablon güncellendi.')
            return redirect('itempool:exam_template_list')
    else:
        form = ExamTemplateForm(instance=tpl)

    import json
    return render(request, 'itempool/exam_template_form.html', {
        'form': form,
        'title': 'Şablon Düzenle',
        'template': tpl,
        'header_design_json': json.dumps(tpl.header_design_json) if tpl.header_design_json else '',
        'footer_design_json': json.dumps(tpl.footer_design_json) if tpl.footer_design_json else '',
    })


@login_required
def template_image_upload(request):
    """GrapesJS Asset Manager için resim yükleme endpoint'i."""
    from django.http import JsonResponse
    import os, uuid

    if request.method != 'POST':
        return JsonResponse({'error': 'POST gerekli'}, status=405)

    uploaded_files = request.FILES.getlist('files[]') or request.FILES.getlist('files')
    if not uploaded_files:
        # Tek dosya gönderilmiş olabilir
        f = request.FILES.get('file')
        if f:
            uploaded_files = [f]

    if not uploaded_files:
        return JsonResponse({'error': 'Dosya bulunamadı'}, status=400)

    from django.conf import settings
    upload_dir = os.path.join(settings.MEDIA_ROOT, 'template_images')
    os.makedirs(upload_dir, exist_ok=True)

    results = []
    for f in uploaded_files:
        ext = os.path.splitext(f.name)[1].lower()
        if ext not in ['.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp']:
            continue
        filename = f"{uuid.uuid4().hex[:12]}{ext}"
        filepath = os.path.join(upload_dir, filename)
        with open(filepath, 'wb+') as dest:
            for chunk in f.chunks():
                dest.write(chunk)
        results.append({
            'src': f"{settings.MEDIA_URL}template_images/{filename}",
            'name': f.name,
        })

    return JsonResponse({'data': results})



@login_required
def exam_template_preview(request, pk):
    """Şablon önizlemesi: kullanıcının en son test formunu örnek olarak kullanır."""
    from django.http import HttpResponse
    from .services.exam_pdf import generate_exam_pdf

    tpl = get_object_or_404(ExamTemplate, pk=pk)
    sample_form = (
        TestForm.objects.filter(created_by=request.user)
        .prefetch_related('form_items')
        .order_by('-id')
        .first()
    )
    if not sample_form:
        messages.warning(request, 'Önizleme için en az bir sınav formu gerekli.')
        return redirect('itempool:exam_template_list')

    pdf_bytes = generate_exam_pdf(sample_form, tpl)
    filename = f"onizleme_{tpl.name[:30].replace(' ', '_')}.pdf"
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="{filename}"'
    return response


@login_required
@transaction.atomic
def test_form_auto_balance(request, pk):
    test_form = get_object_or_404(TestForm, id=pk)
    
    if test_form.status == TestForm.Status.APPLIED:
        messages.error(request, 'Uygulanmış bir sınavın seçenekleri değiştirilemez.')
        return redirect('itempool:test_form_detail', pk=pk)
        
    FormService.balance_choice_distribution(test_form)
    messages.success(request, 'Seçenekler karıştırıldı ve doğru cevap dağılımı dengelendi.')
    
    if request.headers.get('HX-Request') == 'true':
        response = HttpResponse("")
        response['HX-Refresh'] = 'true'
        return response
        
    return redirect('itempool:test_form_detail', pk=pk)

@login_required
def test_form_pdf(request, pk):
    """Test formundan PDF sınav kağıdı üret ve döndür."""
    from django.http import HttpResponse
    from .services.exam_pdf import generate_exam_pdf

    test_form = get_object_or_404(TestForm, pk=pk)
    template_id = request.GET.get('template')
    with_answer_key = request.GET.get('answer_key') == '1'

    if template_id:
        exam_template = get_object_or_404(ExamTemplate, pk=template_id)
    else:
        exam_template = ExamTemplate.get_default()
        if not exam_template:
            messages.error(request, 'Henüz bir sınav kağıdı şablonu tanımlanmamış.')
            return redirect('itempool:test_form_detail', pk=pk)

    pdf_bytes = generate_exam_pdf(test_form, exam_template, with_answer_key=with_answer_key)

    filename = f"sinav_{test_form.id}_{test_form.name[:30].replace(' ', '_')}.pdf"
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="{filename}"'
    return response


# ============================================================
# Faz 13 — Değerlendirme Entegrasyonu Güçlendirme
# ============================================================

@login_required
def test_form_answer_key(request, pk):
    """TestForm'dan cevap anahtarı üretir ve UploadSession'a aktarma seçeneği sunar."""
    from .services.answer_key import generate_answer_key_from_form
    from django.http import JsonResponse

    test_form = get_object_or_404(TestForm, pk=pk)
    answer_key = generate_answer_key_from_form(test_form)

    # Opsiyonel: doğrudan ilişkili bir UploadSession'a aktar
    session_id = request.GET.get('apply_to_session')
    if session_id and request.method == 'POST':
        from grading.models import UploadSession
        session = get_object_or_404(UploadSession, pk=session_id, owner=request.user)
        session.answer_key = answer_key
        session.test_form = test_form
        session.save(update_fields=['answer_key', 'test_form'])
        messages.success(request, f'Cevap anahtarı ({len(answer_key)} soru) oturuma aktarıldı.')
        return redirect('grading:session_detail', pk=session_id)

    return JsonResponse({'answer_key': answer_key, 'question_count': len(answer_key)})


@login_required
def outcome_performance_report(request, session_pk):
    """Bir UploadSession için öğrenme çıktısı bazında başarı raporu."""
    from grading.models import UploadSession
    from .services.answer_key import get_outcome_performance

    session = get_object_or_404(UploadSession, pk=session_pk, owner=request.user)

    if not session.test_form:
        messages.warning(request, 'Bu oturum için ilişkili bir test formu tanımlanmamış.')
        return redirect('grading:session_detail', pk=session_pk)

    performance = get_outcome_performance(session)
    student_count = session.results.count()

    return render(request, 'itempool/outcome_performance_report.html', {
        'session': session,
        'test_form': session.test_form,
        'performance': performance,
        'student_count': student_count,
    })


@login_required
def test_form_docx(request, pk):
    """Sınav formunu Word formatında indirir."""
    test_form = get_object_or_404(TestForm, pk=pk)
    
    template_id = request.GET.get('template')
    with_answer_key = request.GET.get('key') == '1'
    
    if template_id:
        exam_template = get_object_or_404(ExamTemplate, pk=template_id)
    else:
        exam_template = ExamTemplate.get_default()

    from .services.exam_docx import generate_exam_docx
    docx_stream = generate_exam_docx(test_form, exam_template, with_answer_key=with_answer_key)
    
    filename = f"{test_form.name}.docx".replace(" ", "_")
    response = HttpResponse(
        docx_stream.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response



# ============================================================
# Faz 27 — Sinav Formu ↔ Optik Okuma Entegrasyonu (Grading Hub)
# ============================================================


@login_required
def exam_form_upload(request, pk):
    """Bir TestForm icin optik okuma yukleme sayfasi."""
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
    """Bir TestForm icin merkezi analiz paneli."""
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
    """Standalone mod - sadece UploadSession bazli analiz."""
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
    """Bir UploadSession u bir TestForm a baglar."""
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
