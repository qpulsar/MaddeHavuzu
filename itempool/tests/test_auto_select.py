import pytest
from itempool.models import Course, ItemPool, Item, ItemInstance, TestForm, FormItem, CourseSpecTable
from itempool.views import _auto_select_items

@pytest.mark.django_db
def test_auto_select_items_fallback(db, user):
    course = Course.objects.create(name="Test Dersi", semester="2026-Güz", created_by=user)
    pool = ItemPool.objects.create(name="Test Havuzu", owner=user)
    course.pools.add(pool)

    # 10 adet madde ve instance oluştur
    for i in range(10):
        item = Item.objects.create(stem=f"Soru {i}", item_type="MCQ", difficulty_intended="MEDIUM")
        inst = ItemInstance.objects.create(item=item, pool=pool, added_by=user)

    test_form = TestForm.objects.create(
        course=course,
        name="Auto Form Test",
        created_by=user,
        generation_metadata={
            'method': 'AUTO',
            'total_questions': 5,
            'difficulty': 'MIXED',
            'item_type_counts': {'MCQ': 0},
            'excluded_form_ids': []
        }
    )
    test_form.pools.add(pool)

    # Otomatik soru seçimini çalıştır
    _auto_select_items(test_form, course)

    # 5 sorunun başarıyla seçilmiş olması gerekir
    assert test_form.form_items.count() == 5


@pytest.mark.django_db
def test_auto_select_items_with_course_spec_table(db, user):
    course = Course.objects.create(name="Psikoloji Dersi", semester="2026-Güz", created_by=user)
    pool = ItemPool.objects.create(name="Psikoloji Havuzu", owner=user)
    course.pools.add(pool)

    spec_table = CourseSpecTable.objects.create(
        course=course,
        name="Vize Belirtke Tablosu",
        rows_json=[
            {
                "topic": "Temel Kavramlar",
                "outcomes": [{"outcome_id": 999, "question_count": 3}],
                "total_questions": 3
            }
        ]
    )

    for i in range(5):
        item = Item.objects.create(stem=f"Psikoloji Sorusu {i}", item_type="MCQ")
        ItemInstance.objects.create(item=item, pool=pool, added_by=user)

    test_form = TestForm.objects.create(
        course=course,
        name="Spec Table Form Test",
        created_by=user,
        generation_metadata={
            'method': 'AUTO',
            'spec_table_id': spec_table.id,
            'total_questions': 4,
            'difficulty': 'MIXED',
            'item_type_counts': {},
            'excluded_form_ids': []
        }
    )
    test_form.pools.add(pool)

    # NameError vermeden çalışmalı ve eksik soruları fallback ile 4 soruya tamamlamalı
    _auto_select_items(test_form, course)

    assert test_form.form_items.count() == 4
