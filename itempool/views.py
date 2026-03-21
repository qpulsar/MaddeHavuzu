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
    TestForm, FormItem, Blueprint, PoolPermission, ItemAuditLog, StudentGroup, ExamApplication, ExamTemplate
)
from .mixins import PoolAccessMixin
from .forms import (
    ItemPoolForm, LearningOutcomeForm, ItemForm, ItemChoiceFormSet, TestFormForm, BlueprintForm,
    StudentGroupForm, ExamApplicationForm
)
from .services.import_docx import DocxImportService
from .services.llm_client import get_llm_client
import json
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
        
        # Havuzdaki test formları
        context['test_forms'] = self.object.test_forms.all().order_by('-created_at')
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
                # Hatalı formu geri dönerek kullanıcının görmesini sağlayalım.
                # Basitlik için sadece hata mesajı da dönebiliriz ama formu dönmek daha iyidir.
                error_msg = ", ".join([f"{k}: {v[0]}" for k, v in form.errors.items()])
                return HttpResponse(f'<div class="alert alert-danger py-1 small mb-0">{error_msg}</div>', status=200)
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
def test_form_create(request, pool_id):
    pool = get_object_or_404(ItemPool, id=pool_id)
    if request.method == 'POST':
        form = TestFormForm(request.POST)
        if form.is_valid():
            test_form = form.save(commit=False)
            test_form.pool = pool
            test_form.created_by = request.user
            test_form.save()
            
            method = form.cleaned_data['creation_method']
            if method == 'MANUAL':
                return redirect('itempool:test_form_edit_items', pk=test_form.id)
            elif method == 'BLUEPRINT':
                return redirect('itempool:test_form_wizard_blueprint', pk=test_form.id)
            # Spec Table henüz eklenmedi
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
    return render(request, 'itempool/test_form_detail.html', {
        'form': test_form,
        'items': items,
        'total_points': total_points,
        'item_count': item_count,
        'exam_templates': exam_templates,
    })

@login_required
def test_form_edit_items(request, pk):
    test_form = get_object_or_404(TestForm, id=pk)
    pool = test_form.pool
    
    # Mevcut maddeler ve havuzdaki tüm maddeler
    form_item_ids = test_form.form_items.values_list('item_instance_id', flat=True)
    available_items = pool.item_instances.exclude(id__in=form_item_ids)
    
    return render(request, 'itempool/test_form_edit_items.html', {
        'form': test_form,
        'available_items': available_items,
        'current_items': test_form.form_items.all()
    })

@login_required
def test_form_add_item(request, pk, instance_id):
    test_form = get_object_or_404(TestForm, id=pk)
    instance = get_object_or_404(ItemInstance, id=instance_id, pool=test_form.pool)
    
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
    pool = test_form.pool
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
        distribution = blueprint.distribution_json
        for oc_id, count in distribution.items():
            items = ItemInstance.objects.filter(
                pool=blueprint.pool, 
                learning_outcomes__id=oc_id
            ).order_by('?')[:count]
            
            for inst in items:
                FormItem.objects.create(
                    form=test_form,
                    item_instance=inst,
                    order=current_order
                )
                current_order += 1

@login_required
def blueprint_clone(request, pk):
    blueprint = get_object_or_404(Blueprint, pk=pk)
    
    # Yeni bir TestForm oluştur ve bu blueprint'i kullan
    new_form_name = f"{blueprint.name} - Klon"
    new_form = TestForm.objects.create(
        pool=blueprint.pool,
        name=new_form_name,
        created_by=request.user,
        generation_metadata={'cloned_from_blueprint': blueprint.id}
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

    forms = TestForm.objects.filter(pool_id=pool_id).order_by('-created_at')
    return render(request, 'itempool/partials/analysis_form_options.html', {'forms': forms})


# ============================================================
# Faz 11 — Öğrenci Grubu ve Sınav Uygulama View'ları
# ============================================================

@login_required
def student_group_list(request):
    groups = StudentGroup.objects.filter(created_by=request.user).order_by('-created_at')
    return render(request, 'itempool/student_group_list.html', {'groups': groups})


@login_required
def student_group_create(request):
    if request.method == 'POST':
        form = StudentGroupForm(request.POST)
        if form.is_valid():
            group = form.save(commit=False)
            group.created_by = request.user
            group.save()
            messages.success(request, 'Öğrenci grubu oluşturuldu.')
            return redirect('itempool:student_group_list')
    else:
        form = StudentGroupForm()
    return render(request, 'itempool/student_group_form.html', {'form': form, 'title': 'Yeni Grup'})


@login_required
def student_group_detail(request, pk):
    group = get_object_or_404(StudentGroup, pk=pk, created_by=request.user)
    applications = group.exam_applications.select_related('test_form').order_by('-applied_at')
    return render(request, 'itempool/student_group_detail.html', {
        'group': group,
        'applications': applications,
    })


@login_required
def exam_application_create(request, group_pk=None):
    initial = {}
    group = None
    if group_pk:
        group = get_object_or_404(StudentGroup, pk=group_pk, created_by=request.user)
        initial['group'] = group

    if request.method == 'POST':
        form = ExamApplicationForm(request.POST)
        if form.is_valid():
            app = form.save(commit=False)
            app.created_by = request.user
            app.save()
            messages.success(request, 'Sınav uygulaması kaydedildi.')
            return redirect('itempool:student_group_detail', pk=app.group.pk)
    else:
        form = ExamApplicationForm(initial=initial)
    return render(request, 'itempool/exam_application_form.html', {
        'form': form,
        'group': group,
        'title': 'Sınav Uygulaması Kaydet'
    })


@login_required
def exam_application_delete(request, pk):
    app = get_object_or_404(ExamApplication, pk=pk, created_by=request.user)
    group_pk = app.group.pk
    if request.method == 'POST':
        app.delete()
        messages.success(request, 'Sınav uygulaması silindi.')
    return redirect('itempool:student_group_detail', pk=group_pk)


@login_required
def group_applied_items(request, group_pk):
    """Bir gruba daha önce uygulanan madde instance ID'lerini JSON döndürür (soru tekrar filtresi için)."""
    from django.http import JsonResponse
    group = get_object_or_404(StudentGroup, pk=group_pk, created_by=request.user)
    applied_ids = list(group.get_applied_item_instance_ids())
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
        form = ExamTemplateForm(request.POST)
        if form.is_valid():
            tpl = form.save(commit=False)
            tpl.created_by = request.user
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
        form = ExamTemplateForm(request.POST, instance=tpl)
        if form.is_valid():
            form.save()
            messages.success(request, 'Şablon güncellendi.')
            return redirect('itempool:exam_template_list')
    else:
        form = ExamTemplateForm(instance=tpl)
    return render(request, 'itempool/exam_template_form.html', {'form': form, 'title': 'Şablon Düzenle', 'template': tpl})


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

