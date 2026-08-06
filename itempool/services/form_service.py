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
                choices_list = [dict(c) for c in fi.get_choices()]
                
                # Doğru cevabı bul ve listeden çıkar
                correct_idx = next((i for i, c in enumerate(choices_list) if c.get('is_correct')), None)
                if correct_idx is None:
                    random.shuffle(choices_list)
                    final_list = choices_list
                else:
                    correct_choice = choices_list.pop(correct_idx)
                    random.shuffle(choices_list)
                    target_idx = valid_labels.index(target_label)
                    final_list = choices_list[:target_idx] + [correct_choice] + choices_list[target_idx:]
                
                # 5. Overrides JSON oluştur ve kaydet (sadece bu sınav formuna özel)
                overrides = []
                for i, c in enumerate(final_list):
                    overrides.append({
                        'label': labels[i] if i < len(labels) else str(i),
                        'text': c.get('text', ''),
                        'is_correct': bool(c.get('is_correct', False))
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

    @staticmethod
    def generate_booklets(master_test_form, booklet_codes=None, shuffle_questions=True, shuffle_choices=True):
        """
        master_test_form'a bağlı türetilmiş kitapçıkları (A, B, C, D...) oluşturur veya günceller.
        
        :param master_test_form: Ana TestForm nesnesi (Kitapçık A)
        :param booklet_codes: ['A', 'B', 'C', 'D'] gibi liste (Varsayılan: ['A', 'B'])
        :param shuffle_questions: Soruların sırası karıştırılsın mı?
        :param shuffle_choices: Seçeneklerin yerleri karıştırılsın / dengelensin mi?
        :return: Oluşturulan / güncellenen TestForm nesnelerinin listesi
        """
        from itempool.models import TestForm, FormItem

        if booklet_codes is None:
            booklet_codes = ['A', 'B']

        # Master formun kitapçık kodunu A olarak ayarla
        master_test_form.booklet_code = booklet_codes[0] if booklet_codes else 'A'
        master_test_form.save(update_fields=['booklet_code'])

        # Mevcut türetilmiş eski kitapçıkları sil (temiz başlangıç)
        master_test_form.booklets.all().delete()

        master_items = list(master_test_form.form_items.all().order_by('order'))
        if not master_items:
            return [master_test_form]

        created_booklets = [master_test_form]

        # Diğer kitapçıkları türet (ör. B, C, D)
        for code in booklet_codes[1:]:
            booklet_name = f"{master_test_form.name} (Kitapçık {code})"
            derived_form = TestForm.objects.create(
                name=booklet_name,
                description=master_test_form.description,
                course=master_test_form.course,
                status=master_test_form.status,
                created_by=master_test_form.created_by,
                parent_form=master_test_form,
                booklet_code=code,
                generation_metadata={
                    'master_form_id': master_test_form.id,
                    'shuffle_questions': shuffle_questions,
                    'shuffle_choices': shuffle_choices,
                }
            )
            # Master formun bağlı havuzlarını da kopyala
            derived_form.pools.set(master_test_form.pools.all())

            # Soruların sırasını belirle
            items_to_copy = list(master_items)
            if shuffle_questions:
                random.shuffle(items_to_copy)

            # Soru kopyalama ve şık karıştırma
            labels = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J']
            booklet_mapping = {}

            for order, orig_fi in enumerate(items_to_copy, start=1):
                overrides = None
                orig_choices = orig_fi.get_choices()
                if orig_choices and shuffle_choices:
                    choices_copy = [dict(c) for c in orig_choices]
                    random.shuffle(choices_copy)
                    overrides = []
                    for idx, c in enumerate(choices_copy):
                        overrides.append({
                            'label': labels[idx] if idx < len(labels) else str(idx),
                            'text': c.get('text', ''),
                            'is_correct': bool(c.get('is_correct', False))
                        })
                elif orig_choices:
                    overrides = [dict(c) for c in orig_choices]

                FormItem.objects.create(
                    form=derived_form,
                    item_instance=orig_fi.item_instance,
                    order=order,
                    points=orig_fi.points,
                    choice_overrides=overrides
                )
                booklet_mapping[str(order)] = orig_fi.order

            derived_form.generation_metadata['booklet_mapping'] = booklet_mapping
            derived_form.save(update_fields=['generation_metadata'])
            created_booklets.append(derived_form)

        return created_booklets
