import pytest
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
