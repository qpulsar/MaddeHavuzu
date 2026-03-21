"""
Faz 13 — Değerlendirme entegrasyonu testleri.
"""
import pytest
from itempool.models import Item, ItemChoice, ItemInstance, LearningOutcome, TestForm, FormItem
from itempool.services.answer_key import generate_answer_key_from_form, get_outcome_performance


@pytest.mark.django_db
class TestAnswerKeyService:

    def test_generate_answer_key_mcq(self, user, item_pool):
        # Test formu oluştur
        tf = TestForm.objects.create(name='Test', pool=item_pool, created_by=user)

        # 3 MCQ sorusu ekle
        for i, correct_label in enumerate(['A', 'C', 'B']):
            item = Item.objects.create(stem=f'Soru {i+1}', item_type='MCQ', author=user)
            for label in ['A', 'B', 'C', 'D']:
                ItemChoice.objects.create(
                    item=item, label=label, text=f'Seçenek {label}',
                    is_correct=(label == correct_label), order=ord(label) - ord('A')
                )
            instance = ItemInstance.objects.create(pool=item_pool, item=item, added_by=user)
            FormItem.objects.create(form=tf, item_instance=instance, order=i + 1, points=1)

        key = generate_answer_key_from_form(tf)
        assert key == 'ACB'
        assert len(key) == 3

    def test_generate_answer_key_mixed_types(self, user, item_pool):
        tf = TestForm.objects.create(name='Karışık Test', pool=item_pool, created_by=user)

        # MCQ soru
        mcq = Item.objects.create(stem='Soru 1', item_type='MCQ', author=user)
        ItemChoice.objects.create(item=mcq, label='B', text='Doğru', is_correct=True, order=1)
        mcq_inst = ItemInstance.objects.create(pool=item_pool, item=mcq, added_by=user)
        FormItem.objects.create(form=tf, item_instance=mcq_inst, order=1, points=2)

        # Kısa cevap sorusu
        sa = Item.objects.create(stem='Soru 2', item_type='SHORT_ANSWER',
                                  expected_answer='Python', author=user)
        sa_inst = ItemInstance.objects.create(pool=item_pool, item=sa, added_by=user)
        FormItem.objects.create(form=tf, item_instance=sa_inst, order=2, points=3)

        # Açık uçlu soru
        open_item = Item.objects.create(stem='Soru 3', item_type='OPEN', author=user)
        open_inst = ItemInstance.objects.create(pool=item_pool, item=open_item, added_by=user)
        FormItem.objects.create(form=tf, item_instance=open_inst, order=3, points=5)

        key = generate_answer_key_from_form(tf)
        assert key[0] == 'B'   # MCQ doğru cevabı
        assert key[1] == 'K'   # SHORT_ANSWER işareti
        assert key[2] == 'A'   # OPEN işareti

    def test_generate_answer_key_empty_form(self, user, item_pool):
        tf = TestForm.objects.create(name='Boş Form', pool=item_pool, created_by=user)
        key = generate_answer_key_from_form(tf)
        assert key == ''

    def test_uploadsession_test_form_fk(self, user, item_pool):
        """UploadSession'a TestForm FK eklendiğini doğrula."""
        from grading.models import UploadSession
        tf = TestForm.objects.create(name='Test Form', pool=item_pool, created_by=user)

        # Dosya olmadan sadece FK testi için UploadSession oluştur
        session = UploadSession(
            owner=user,
            original_filename='test.txt',
            test_form=tf,
        )
        assert session.test_form == tf
        assert session.test_form.name == 'Test Form'


@pytest.mark.django_db
class TestOutcomePerformance:

    def test_get_outcome_performance_no_test_form(self, user, item_pool):
        """Test formu olmayan oturum için boş liste döner."""
        from grading.models import UploadSession
        session = UploadSession(owner=user, original_filename='t.txt', test_form=None)
        result = get_outcome_performance(session)
        assert result == []
