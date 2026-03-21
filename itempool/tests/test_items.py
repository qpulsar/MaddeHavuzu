import pytest
from django.core.exceptions import ValidationError
from itempool.models import Item, ItemChoice, ItemInstance, LearningOutcome

@pytest.mark.django_db
class TestItemModels:
    def test_create_item_with_choices(self, user):
        item = Item.objects.create(
            stem='Türkiye\'nin başkenti neresidir?',
            item_type='MCQ',
            difficulty_intended='EASY',
            author=user
        )
        
        ItemChoice.objects.create(item=item, label='A', text='İstanbul', is_correct=False)
        ItemChoice.objects.create(item=item, label='B', text='Ankara', is_correct=True)
        
        assert item.choices.count() == 2
        assert item.choices.filter(is_correct=True).first().text == 'Ankara'

    def test_item_instance_in_pool(self, item_pool, user):
        item = Item.objects.create(
            stem='Soru 1',
            author=user
        )
        
        outcome = LearningOutcome.objects.create(
            pool=item_pool, 
            code='ÖÇ1', 
            description='Test'
        )
        
        instance = ItemInstance.objects.create(
            pool=item_pool,
            item=item,
            added_by=user
        )
        instance.learning_outcomes.add(outcome)
        
        assert instance.pool == item_pool
        assert instance.item == item
        assert instance.learning_outcomes.filter(id=outcome.id).exists()

    def test_item_instance_unique_constraint(self, item_pool, user):
        item = Item.objects.create(stem='Soru 1', author=user)
        ItemInstance.objects.create(pool=item_pool, item=item, added_by=user)
        
        with pytest.raises(Exception): # IntegrityError
            ItemInstance.objects.create(pool=item_pool, item=item, added_by=user)

    # --- Faz 10: Yeni soru tipleri testleri ---

    def test_short_answer_item(self, user):
        item = Item.objects.create(
            stem='Python\'da liste nasıl tanımlanır?',
            item_type=Item.ItemType.SHORT_ANSWER,
            expected_answer='Köşeli parantez kullanılır: [1, 2, 3]',
            author=user
        )
        assert item.item_type == 'SHORT_ANSWER'
        assert item.expected_answer is not None
        assert item.choices.count() == 0

    def test_open_ended_item(self, user):
        item = Item.objects.create(
            stem='Yazılım mühendisliğinin önemi hakkında kısaca yazınız.',
            item_type=Item.ItemType.OPEN_ENDED,
            scoring_rubric='Tam puan: Tüm ana kavramlar açıklandı. Yarım puan: En az 2 kavram açıklandı.',
            author=user
        )
        assert item.item_type == 'OPEN'
        assert item.scoring_rubric is not None

    def test_mcq_max_choices_default(self, user):
        item = Item.objects.create(stem='Soru', item_type='MCQ', author=user)
        assert item.max_choices == 4

    def test_mcq_max_choices_custom(self, user):
        item = Item.objects.create(stem='Soru', item_type='MCQ', max_choices=5, author=user)
        assert item.max_choices == 5

    def test_mcq_max_choices_validation(self, user):
        item = Item(stem='Soru', item_type='MCQ', max_choices=11, author=user)
        with pytest.raises(ValidationError):
            item.full_clean()

    def test_mcq_max_choices_min_validation(self, user):
        item = Item(stem='Soru', item_type='MCQ', max_choices=1, author=user)
        with pytest.raises(ValidationError):
            item.full_clean()

    def test_mcq_10_choices(self, user):
        item = Item.objects.create(stem='Soru', item_type='MCQ', max_choices=10, author=user)
        labels = list('ABCDEFGHIJ')
        for i, label in enumerate(labels):
            ItemChoice.objects.create(item=item, label=label, text=f'Seçenek {label}', order=i)
        assert item.choices.count() == 10

    def test_forking_item(self, item_pool, user):
        # Orijinal madde
        item1 = Item.objects.create(stem='Orijinal Soru', author=user)
        instance1 = ItemInstance.objects.create(pool=item_pool, item=item1, added_by=user)
        
        # Yeni havuz
        from itempool.models import ItemPool
        pool2 = ItemPool.objects.create(name='P2', course='C2', semester='S2', level='L', owner=user)
        
        # Fork (kopyalama) işlemi
        item2 = Item.objects.create(stem='Orijinal Soru (Kopya)', author=user, version=2)
        instance2 = ItemInstance.objects.create(
            pool=pool2, 
            item=item2, 
            is_fork=True, 
            forked_from=instance1,
            added_by=user
        )
        
        assert instance2.is_fork is True
        assert instance2.forked_from == instance1
