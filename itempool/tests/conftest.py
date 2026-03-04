import pytest
from django.contrib.auth.models import User
from itempool.models import ItemPool

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
