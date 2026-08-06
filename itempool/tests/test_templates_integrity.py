import os
import pytest
from django.template.loader import get_template
from django.template import Context
from django.conf import settings


@pytest.mark.django_db
def test_all_templates_compile_and_load():
    """
    itempool ve grading uygulamalarındaki tüm HTML şablonlarının (templates)
    düzgün ayrıştırılabildiğini (parse) ve derlenebildiğini doğrular.
    """
    templates_dirs = [
        os.path.join(settings.BASE_DIR, 'itempool', 'templates'),
        os.path.join(settings.BASE_DIR, 'grading', 'templates'),
    ]

    loaded_count = 0
    errors = []

    for t_dir in templates_dirs:
        if not os.path.exists(t_dir):
            continue

        for root, _, files in os.walk(t_dir):
            for file in files:
                if file.endswith('.html'):
                    full_path = os.path.join(root, file)
                    rel_path = os.path.relpath(full_path, t_dir)
                    try:
                        tpl = get_template(rel_path)
                        assert tpl is not None
                        loaded_count += 1
                    except Exception as e:
                        errors.append(f"{rel_path}: {e}")

    assert not errors, f"Şablon derleme hataları bulundu: {errors}"
    assert loaded_count > 0, "Hiç şablon yüklenemedi."


@pytest.mark.django_db
def test_key_templates_render_without_crash(user, item_pool):
    """
    Kritik şablonların varsayılan/boş bağlam (context) ile render edildiğinde
    çökmediğini ve tanımsız değişken patlaması yaşanmadığını doğrular.
    """
    from itempool.models import TestForm, Course

    course = Course.objects.create(
        name="Test Dersi",
        code="TEST101",
        semester="2026-Güz",
        created_by=user
    )
    test_form = TestForm.objects.create(
        name="Vize Sınavı",
        course=course,
        created_by=user,
        generation_metadata={"warnings": ["Test uyarısı"]}
    )

    from itempool.models import ExamTemplate
    exam_tpl = ExamTemplate.objects.create(
        name="Standart Şablon",
        created_by=user
    )

    templates_to_test = [
        ('itempool/test_form_detail.html', {'form': test_form, 'items': [], 'distribution': {}, 'exam_templates': [exam_tpl]}),
        ('itempool/course_detail.html', {'course': course, 'test_forms': [test_form], 'spec_tables': []}),
        ('itempool/pool_detail.html', {'pool': item_pool, 'items': [], 'outcomes': []}),
        ('itempool/partials/template_card.html', {'tpl': exam_tpl, 'template': exam_tpl}),
    ]

    for tpl_name, context in templates_to_test:
        try:
            tpl = get_template(tpl_name)
            rendered = tpl.render(context)
            assert isinstance(rendered, str)
        except Exception as e:
            pytest.fail(f"Şablon render hatası ({tpl_name}): {e}")
