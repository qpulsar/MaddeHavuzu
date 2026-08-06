import pytest
from django.urls import reverse
from itempool.models import TestForm, FormItem, Blueprint, Item, ItemInstance, LearningOutcome

@pytest.fixture
def test_form(db, item_pool, user):
    tf = TestForm.objects.create(
        name='Bahar Vize',
        created_by=user
    )
    tf.pools.add(item_pool)
    return tf

@pytest.fixture
def blueprint(db, item_pool, user):
    return Blueprint.objects.create(
        name='Vize Şablonu',
        pool=item_pool,
        distribution_json={'1': 5},
        total_items=5,
        created_by=user
    )

@pytest.mark.django_db
class TestFormViews:
    def test_test_form_create_view(self, client, user, item_pool):
        from itempool.models import Course
        course = Course.objects.create(name="Eğitim Psikolojisi", semester="2026-Güz", created_by=user)
        course.pools.add(item_pool)

        client.force_login(user)
        url = reverse('itempool:course_test_form_create', kwargs={'course_pk': course.id})
        data = {
            'name': 'Güz Final',
            'description': 'Final sınavı formu',
            'status': 'DRAFT',
            'pools': [item_pool.id]
        }
        response = client.post(url, data)
        assert response.status_code in [200, 302]
        assert TestForm.objects.filter(name='Güz Final').exists()

    def test_test_form_add_item(self, client, user, test_form):
        client.force_login(user)
        item = Item.objects.create(stem='Test Soru 1', author=user)
        instance = ItemInstance.objects.create(pool=test_form.pools.first(), item=item, added_by=user)
        
        url = reverse('itempool:test_form_add_item', kwargs={'pk': test_form.id, 'instance_id': instance.id})
        response = client.post(url, HTTP_HX_REQUEST='true')
        assert response.status_code == 200
        assert FormItem.objects.filter(form=test_form, item_instance=instance).exists()

    def test_blueprint_clone(self, client, user, item_pool, blueprint):
        client.force_login(user)
        oc = LearningOutcome.objects.create(id=1, pool=item_pool, code='ÖÇ1', description='D1')
        for i in range(5):
            it = Item.objects.create(stem=f'Soru {i}', author=user)
            inst = ItemInstance.objects.create(pool=item_pool, item=it, added_by=user)
            inst.learning_outcomes.add(oc)

        url = reverse('itempool:blueprint_clone', kwargs={'pk': blueprint.id})
        response = client.post(url)
        assert response.status_code == 302
        
        cloned_form = TestForm.objects.filter(name__icontains='Klon').first()
        assert cloned_form is not None
        assert cloned_form.form_items.count() == 5
