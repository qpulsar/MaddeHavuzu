import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from itempool.models import ItemPool, LearningOutcome, Item, ItemInstance
from itempool.services.import_excel_outcomes import ExcelOutcomeImportService
from itempool.services.similarity import SimilarityService

@pytest.mark.django_db
def test_excel_outcome_import_csv():
    from django.contrib.auth.models import User
    user = User.objects.create_user(username="testuser", password="password")
    pool = ItemPool.objects.create(name="Test Pool", owner=user)
    csv_data = "Kod,Açıklama,Düzey,Konu,Sıra\nÖÇ-100,Test Çıktısı Açıklaması,Anlama,Konu 1,1\n"
    uploaded_file = SimpleUploadedFile("outcomes.csv", csv_data.encode('utf-8'), content_type="text/csv")
    
    service = ExcelOutcomeImportService(pool.id, uploaded_file)
    created, updated = service.process()
    
    assert created == 1
    assert LearningOutcome.objects.filter(pool=pool, code="ÖÇ-100").exists()

@pytest.mark.django_db
def test_duplicate_candidate_detection():
    from django.contrib.auth.models import User
    user = User.objects.create_user(username="testuser2", password="password")
    pool = ItemPool.objects.create(name="Duplicate Test Pool", owner=user)
    item = Item.objects.create(
        stem="Aşağıdakilerden hangisi hücre zarının temel görevlerinden biridir?",
        item_type="MCQ"
    )
    ItemInstance.objects.create(pool=pool, item=item, added_by=user)
    
    # Benzer metin sorgusu
    query_stem = "Aşağıdakilerden hangisi hücre zarının temel görevlerindendir?"
    similar_item, ratio = SimilarityService.find_duplicate_candidates(query_stem, pool_id=pool.id, threshold=0.65)
    
    assert similar_item is not None
    assert similar_item.id == item.id
    assert ratio >= 65.0
