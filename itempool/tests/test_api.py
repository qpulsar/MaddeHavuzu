import pytest
from django.urls import reverse
from rest_framework.test import APIClient
from itempool.models import LearningOutcome

@pytest.fixture
def api_client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client

@pytest.mark.django_db
class TestLearningOutcomeAPI:
    def test_list_outcomes(self, api_client, item_pool):
        # Önce bir çıktı oluşturalım
        LearningOutcome.objects.create(
            pool=item_pool, 
            code='ÖÇ1', 
            description='Test Çıktısı',
            level='KNOWLEDGE'
        )
        
        url = reverse('itempool:api_outcome_list_create', kwargs={'pool_id': item_pool.id})
        response = api_client.get(url)
        
        assert response.status_code == 200
        # DRF Pagination varsa veri 'results' içinde olur
        data = response.data.get('results', response.data)
        assert len(data) == 1
        assert data[0]['code'] == 'ÖÇ1'

    def test_create_outcome(self, api_client, item_pool):
        url = reverse('itempool:api_outcome_list_create', kwargs={'pool_id': item_pool.id})
        data = {
            'code': 'ÖÇ2',
            'description': 'Yeni API Çıktısı',
            'level': 'APPLICATION',
            'weight': 20.0,
            'order': 2
        }
        response = api_client.post(url, data)
        
        assert response.status_code == 201
        assert LearningOutcome.objects.filter(code='ÖÇ2', pool=item_pool).exists()

    def test_update_outcome(self, api_client, item_pool):
        outcome = LearningOutcome.objects.create(
            pool=item_pool, 
            code='ÖÇ3', 
            description='Eski Açıklama'
        )
        url = reverse('itempool:api_outcome_detail', kwargs={'pk': outcome.id})
        data = {'description': 'Güncel Açıklama'}
        response = api_client.patch(url, data)
        
        assert response.status_code == 200
        outcome.refresh_from_db()
        assert outcome.description == 'Güncel Açıklama'

    def test_delete_outcome(self, api_client, item_pool):
        outcome = LearningOutcome.objects.create(
            pool=item_pool, 
            code='ÖÇ4', 
            description='Silinecek'
        )
        url = reverse('itempool:api_outcome_detail', kwargs={'pk': outcome.id})
        response = api_client.delete(url)
        
        assert response.status_code == 204
        assert not LearningOutcome.objects.filter(id=outcome.id).exists()
