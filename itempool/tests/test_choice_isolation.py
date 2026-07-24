import pytest
from itempool.models import Item, ItemChoice, ItemInstance, TestForm, FormItem
from itempool.services.form_service import FormService
from itempool.services.answer_key import generate_answer_key_from_form


@pytest.mark.django_db
def test_choice_isolation_between_pool_and_exam(user, item_pool):
    # 1. Havuzda bir MCQ sorusu ve şıkları oluştur (Doğru cevap A)
    item = Item.objects.create(stem='Dünyanın şekli nedir?', item_type='MCQ', author=user)
    choice_a = ItemChoice.objects.create(item=item, label='A', text='Geoid', is_correct=True, order=1)
    choice_b = ItemChoice.objects.create(item=item, label='B', text='Küp', is_correct=False, order=2)
    choice_c = ItemChoice.objects.create(item=item, label='C', text='Piramit', is_correct=False, order=3)
    choice_d = ItemChoice.objects.create(item=item, label='D', text='Düz', is_correct=False, order=4)

    instance = ItemInstance.objects.create(pool=item_pool, item=item, added_by=user)

    # 2. Sınav Formu 1 oluştur
    form1 = TestForm.objects.create(name='Sınav 1', created_by=user)
    form1.pools.add(item_pool)
    fi1 = FormItem.objects.create(form=form1, item_instance=instance, order=1)

    # FormItem oluştuduğu anda şık snapshot'ının dondurulduğunu doğrula
    assert fi1.choice_overrides is not None
    assert len(fi1.choice_overrides) == 4
    assert generate_answer_key_from_form(form1) == 'A'

    # 3. Havuzdaki sorunun şıklarını sonradan değiştir (Örn: B şıkkını doğru cevap yap)
    choice_a.is_correct = False
    choice_a.save()
    choice_b.is_correct = True
    choice_b.save()

    # Sınav 1'in doğru cevabının HAVUZ DEĞİŞİKLİĞİNDEN ETKİLENMEDİĞİNİ doğrula
    assert generate_answer_key_from_form(form1) == 'A'

    # 4. Sınav Formu 2 oluştur ve "Seçenekleri Dengele" çalıştır
    form2 = TestForm.objects.create(name='Sınav 2', created_by=user)
    form2.pools.add(item_pool)
    fi2 = FormItem.objects.create(form=form2, item_instance=instance, order=1)

    FormService.balance_choice_distribution(form2)
    fi2.refresh_from_db()

    # Dengelemenin SADECE Sınav 2'nin choice_overrides nesnesini değiştirdiğini
    # Sınav 1'in ve Havuzdaki nesnelerin değişmediğini doğrula
    fi1.refresh_from_db()
    assert generate_answer_key_from_form(form1) == 'A'
    assert item.choices.count() == 4
