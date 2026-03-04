import pytest
from django.urls import reverse
from django.contrib.auth.models import User
from itempool.models import ItemPool, LearningOutcome

@pytest.fixture
def user(db):
    return User.objects.create_user(username='testuser', password='password123')

@pytest.fixture
def item_pool(db, user):
    return ItemPool.objects.create(
        name='Test Havuzu',
        course='Fizik 101',
        semester='2024-Bahar',
        level='Lisans 1',
        owner=user,
        status=ItemPool.Status.ACTIVE
    )

@pytest.mark.django_db
class TestItemPoolModels:
    def test_create_item_pool(self, user):
        pool = ItemPool.objects.create(
            name='Matematik',
            course='Mat 101',
            semester='2024-Bahar',
            level='Lisans',
            owner=user
        )
        assert pool.name == 'Matematik'
        assert str(pool) == 'Matematik (2024-Bahar)'
        assert pool.status == 'ACTIVE'

    def test_create_learning_outcome(self, item_pool):
        outcome = LearningOutcome.objects.create(
            pool=item_pool,
            code='FİZ-1',
            description='Temel fizik kavramlarını tanımlar',
            level=LearningOutcome.BloomLevel.KNOWLEDGE,
            order=1
        )
        assert outcome.code == 'FİZ-1'
        assert outcome.pool == item_pool
        assert str(outcome) == 'FİZ-1 - Temel fizik kavramlarını tanımlar'


@pytest.mark.django_db
class TestItemPoolViews:
    def test_pool_list_view(self, client, user, item_pool):
        client.force_login(user)
        url = reverse('itempool:pool_list')
        response = client.get(url)
        assert response.status_code == 200
        assert item_pool.name in response.content.decode('utf-8')

    def test_pool_create_view(self, client, user):
        client.force_login(user)
        url = reverse('itempool:pool_create')
        data = {
            'name': 'Kimya Havuzu',
            'course': 'Kimya 101',
            'semester': '2024-Güz',
            'level': 'Lisans 1',
            'status': 'ACTIVE'
        }
        response = client.post(url, data)
        assert response.status_code == 302  # Başarı durumunda yönlendirir
        assert ItemPool.objects.filter(name='Kimya Havuzu').exists()

    def test_outcome_add_view(self, client, user, item_pool):
        client.force_login(user)
        url = reverse('itempool:outcome_add', kwargs={'pool_id': item_pool.id})
        data = {
            'code': 'KİM-1',
            'description': 'Kimyasal bağları kavrar.',
            'level': 'COMPREHENSION',
            'weight': 10.0,
            'order': 1
        }
        response = client.post(url, data)
        assert response.status_code == 302
        assert LearningOutcome.objects.filter(code='KİM-1').exists()
