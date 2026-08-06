import pytest
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from itempool.models import TestForm, FormItem, ItemPool, Item, ItemChoice, ItemInstance
from itempool.services.form_service import FormService
from itempool.services.answer_key import generate_answer_key_from_form
from grading.models import UploadSession, FileFormatConfig


@pytest.mark.django_db
class TestBookletGeneration:
    def setup_method(self):
        from django.contrib.auth.models import User
        self.user = User.objects.create_user(username='testuser', password='password123')
        self.pool = ItemPool.objects.create(name='Test Pool', owner=self.user)
        self.master_form = TestForm.objects.create(name='Vize Sınavı', created_by=self.user)
        self.master_form.pools.add(self.pool)

        # 3 Adet çoktan seçmeli soru ekleyelim
        for i in range(1, 4):
            item = Item.objects.create(
                stem=f'Soru Metni {i}',
                item_type=Item.ItemType.MULTIPLE_CHOICE,
                author=self.user
            )
            ItemChoice.objects.create(item=item, label='A', text=f'Soru {i} A Şıkkı', is_correct=(i == 1))
            ItemChoice.objects.create(item=item, label='B', text=f'Soru {i} B Şıkkı', is_correct=(i == 2))
            ItemChoice.objects.create(item=item, label='C', text=f'Soru {i} C Şıkkı', is_correct=(i == 3))
            
            inst = ItemInstance.objects.create(pool=self.pool, item=item, added_by=self.user)
            FormItem.objects.create(form=self.master_form, item_instance=inst, order=i)

    def test_generate_booklets_creates_derived_forms(self):
        booklets = FormService.generate_booklets(
            master_test_form=self.master_form,
            booklet_codes=['A', 'B', 'C', 'D'],
            shuffle_questions=True,
            shuffle_choices=True
        )

        assert len(booklets) == 4
        assert self.master_form.booklet_code == 'A'
        
        derived_booklets = list(self.master_form.booklets.all().order_by('booklet_code'))
        assert len(derived_booklets) == 3
        codes = [b.booklet_code for b in derived_booklets]
        assert codes == ['B', 'C', 'D']

        for b in derived_booklets:
            assert b.form_items.count() == 3
            assert b.parent_form == self.master_form

    def test_booklet_answer_keys_generated_correctly(self):
        FormService.generate_booklets(
            master_test_form=self.master_form,
            booklet_codes=['A', 'B'],
            shuffle_questions=False,
            shuffle_choices=True
        )

        key_a = generate_answer_key_from_form(self.master_form)
        b_form = self.master_form.booklets.filter(booklet_code='B').first()
        key_b = generate_answer_key_from_form(b_form)

        assert len(key_a) == 3
        assert len(key_b) == 3
        # Her soru için 1 doğru cevap olduğu doğrulanır
        assert '?' not in key_a
        assert '?' not in key_b

    def test_booklet_generation_view_post(self, client):
        client.force_login(self.user)
        url = reverse('itempool:test_form_generate_booklets', kwargs={'pk': self.master_form.id})
        data = {
            'booklet_count': '4',
            'shuffle_questions': 'on',
            'shuffle_choices': 'on'
        }
        response = client.post(url, data)
        assert response.status_code in [200, 302]
        
        self.master_form.refresh_from_db()
        assert self.master_form.booklets.count() == 3
