import random
from itempool.models import FormItem

class FormService:
    @staticmethod
    def balance_choice_distribution(test_form):
        """
        TestForm'daki çoktan seçmeli soruların doğru cevap şıklarını (A, B, C...)
        yüzde olarak eşit dağılacak şekilde karıştırır ve FormItem.choice_overrides alanına kaydeder.
        """
        # 1. Filtrele: Sadece MCQ ve TF olan, şıkkı olan maddeleri al
        form_items = list(test_form.form_items.filter(
            item_instance__item__item_type__in=['MCQ', 'TF']
        ).select_related('item_instance__item'))
        
        if not form_items:
            return
            
        # 2. Şık sayısına göre grupla (4 şıklılar ve 5 şıklılar ayrı dengelenmeli)
        items_by_choice_count = {}
        for fi in form_items:
            c_count = fi.item_instance.item.choices.count()
            if c_count > 1: # En az 2 şık olmalı (TF dahil)
                items_by_choice_count.setdefault(c_count, []).append(fi)
        
        labels = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J']
        
        for c_count, items in items_by_choice_count.items():
            # Bu şık sayısı için geçerli etiketler (Örn: 5 şık için A, B, C, D, E)
            valid_labels = labels[:c_count]
            
            # 3. İdeal dağılım için hedef kümesi oluştur
            # Örn: 10 soru, 4 şık → [A, B, C, D, A, B, C, D, A, B]
            target_labels = (valid_labels * (len(items) // c_count + 1))[:len(items)]
            random.shuffle(target_labels)
            
            # 4. Her madde için şıkları karıştır ve doğru cevabı hedef harfe oturt
            for fi, target_label in zip(items, target_labels):
                item = fi.item_instance.item
                orig_choices = list(item.choices.all())
                
                # Doğru cevabı bul ve listeden çıkar
                correct_idx = next((i for i, c in enumerate(orig_choices) if c.is_correct), None)
                if correct_idx is None:
                    # Doğru cevabı olmayan (hatalı) soruyu sadece karıştır, dengelemeye katma
                    random.shuffle(orig_choices)
                    final_list = orig_choices
                else:
                    correct_choice = orig_choices.pop(correct_idx)
                    # Diğer (yanlış) cevapları kendi arasında karıştır
                    random.shuffle(orig_choices)
                    # Doğru cevabı hedef etiketin olduğu sıraya yerleştir
                    target_idx = valid_labels.index(target_label)
                    final_list = orig_choices[:target_idx] + [correct_choice] + orig_choices[target_idx:]
                
                # 5. Overrides JSON oluştur ve kaydet
                overrides = []
                for i, c in enumerate(final_list):
                    overrides.append({
                        'label': labels[i] if i < len(labels) else str(i),
                        'text': c.text,
                        'is_correct': getattr(c, 'is_correct', False)
                    })
                fi.choice_overrides = overrides
                fi.save()

    @staticmethod
    def get_choice_distribution(test_form):
        """Mevcut doğru cevap dağılımını döner."""
        dist = {}
        form_items = test_form.form_items.all()
        for fi in form_items:
            # Eğer override varsa oradan, yoksa orijinal item'dan al
            correct_label = '?'
            if fi.choice_overrides:
                correct_choice = next((c for c in fi.choice_overrides if c['is_correct']), None)
                if correct_choice:
                    correct_label = correct_choice['label']
            else:
                item = fi.item_instance.item
                if item.item_type in ['MCQ', 'TF']:
                    correct = item.choices.filter(is_correct=True).first()
                    if correct:
                        correct_label = correct.label
            
            if correct_label != '?':
                dist[correct_label] = dist.get(correct_label, 0) + 1
        
        return dict(sorted(dist.items()))
