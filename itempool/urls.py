from django.urls import path
from . import views, views_wizard

app_name = 'itempool'

urlpatterns = [
    # ── Sihirbazlar ──────────────────────────────────────────────────────────
    path('sihirbaz/', views_wizard.wizard_landing, name='wizard_landing'),
    # Havuz sihirbazı
    path('sihirbaz/havuz/adim/1/', views_wizard.wizard_pool_step1, name='wizard_pool_step1'),
    path('sihirbaz/havuz/adim/2/<int:pool_id>/', views_wizard.wizard_pool_step2, name='wizard_pool_step2'),
    path('sihirbaz/havuz/adim/3/<int:pool_id>/', views_wizard.wizard_pool_step3, name='wizard_pool_step3'),
    # Sınav sihirbazı
    path('sihirbaz/sinav/adim/1/', views_wizard.wizard_exam_step1, name='wizard_exam_step1'),
    path('sihirbaz/sinav/adim/2/<int:form_id>/', views_wizard.wizard_exam_step2, name='wizard_exam_step2'),
    path('sihirbaz/sinav/adim/3/<int:form_id>/', views_wizard.wizard_exam_step3, name='wizard_exam_step3'),
    path('sihirbaz/sinav/adim/4/<int:form_id>/', views_wizard.wizard_exam_step4, name='wizard_exam_step4'),
    # Değerlendirme sihirbazı
    path('sihirbaz/degerlendirme/adim/1/', views_wizard.wizard_eval_step1, name='wizard_eval_step1'),
    path('sihirbaz/degerlendirme/adim/2/<int:form_id>/', views_wizard.wizard_eval_step2, name='wizard_eval_step2'),
    path('sihirbaz/degerlendirme/adim/3/<int:session_id>/', views_wizard.wizard_eval_step3, name='wizard_eval_step3'),
    # Global test formu listesi
    path('formlar/', views_wizard.test_form_list_all, name='test_form_list_all'),

    path('', views.ItemPoolListView.as_view(), name='pool_list'),
    path('yeni/', views.ItemPoolCreateView.as_view(), name='pool_create'),
    path('<int:pk>/', views.ItemPoolDetailView.as_view(), name='pool_detail'),
    path('<int:pk>/duzenle/', views.ItemPoolUpdateView.as_view(), name='pool_update'),
    path('<int:pk>/bulk-suggest-outcomes/', views.pool_bulk_suggest_outcomes, name='pool_bulk_suggest_outcomes'),
    
    # Öğrenme Çıktısı HTMX ve Normal Rotalar
    path('<int:pool_id>/outcomes/add/', views.add_learning_outcome, name='outcome_add'),
    path('outcomes/<int:pk>/', views.get_learning_outcome_row, name='outcome_row'),
    path('outcomes/<int:pk>/edit/', views.edit_learning_outcome, name='outcome_edit'),
    path('outcomes/<int:pk>/delete/', views.delete_learning_outcome, name='outcome_delete'),

    # API Rotaları
    path('api/pools/<int:pool_id>/outcomes/', views.LearningOutcomeListCreateAPIView.as_view(), name='api_outcome_list_create'),
    path('api/outcomes/<int:pk>/', views.LearningOutcomeRetrieveUpdateDestroyAPIView.as_view(), name='api_outcome_detail'),

    # Madde (Item) Rotaları
    path('<int:pool_id>/items/yeni/', views.item_create, name='item_create'),
    path('items/<int:pk>/', views.item_detail, name='item_detail'),
    path('items/<int:pk>/sil/', views.item_delete, name='item_delete'),

    # Docx Import Rotaları
    path('<int:pool_id>/import/', views.import_upload, name='import_upload'),
    path('import/<int:batch_id>/preview/', views.import_preview, name='import_preview'),
    path('import/<int:batch_id>/commit/', views.import_commit, name='import_commit'),

    # AI Öneri ve Üretim Rotaları
    path('items/<int:pk>/AI/suggest-outcomes/', views.item_suggest_outcomes, name='item_suggest_outcomes'),
    path('items/<int:pk>/AI/assign-outcome/<int:outcome_id>/', views.item_assign_outcome, name='item_assign_outcome'),
    path('outcomes/<int:pk>/AI/generate/', views.item_generate_ai, name='item_generate_ai'),
    path('AI/suggest-distractors/', views.item_suggest_distractors, name='item_suggest_distractors'),
    path('AI/check-duplicate/', views.item_check_duplicate, name='item_check_duplicate'),
    path('pools/<int:pool_id>/AI/semantic-search/', views.pool_semantic_search, name='pool_semantic_search'),
    path('pools/<int:pool_id>/AI/vectorize-confirm/', views.pool_vectorize_confirm, name='pool_vectorize_confirm'),
    path('pools/<int:pool_id>/AI/vectorize-start/', views.pool_vectorize_start, name='pool_vectorize_start'),
    path('items/<int:pk>/AI/clone-variation/', views.item_clone_variation, name='item_clone_variation'),
    path('items/<int:pk>/AI/suggest-improvements/', views.item_suggest_improvements, name='item_suggest_improvements'),

    # Madde Detay Düzenleme (HTMX)
    path('items/instance/<int:pk>/edit/<str:section>/', views.item_detail_edit, name='item_detail_edit'),
    path('items/instance/<int:pk>/save/<str:section>/', views.item_detail_save, name='item_detail_save'),

    # Test Formu Rotaları
    path('formlar/yeni/', views.test_form_create, name='test_form_create'),
    path('formlar/<int:pk>/', views.test_form_detail, name='test_form_detail'),
    path('formlar/<int:pk>/maddeler/duzenle/', views.test_form_edit_items, name='test_form_edit_items'),
    path('formlar/<int:pk>/wizard/blueprint/', views.test_form_wizard_blueprint, name='test_form_wizard_blueprint'),
    path('formlar/<int:pk>/maddeler/ekle/<int:instance_id>/', views.test_form_add_item, name='test_form_add_item'),
    path('formlar/<int:pk>/maddeler/cikar/<int:item_id>/', views.test_form_remove_item, name='test_form_remove_item'),
    path('blueprints/<int:pk>/klonla/', views.blueprint_clone, name='blueprint_clone'),
    path('analiz/yukle/', views.analysis_upload, name='analysis_upload'),
    path('analiz/get-forms/', views.analysis_get_forms, name='analysis_get_forms'),

    # Ders Rotaları
    path('dersler/', views.course_list, name='course_list'),
    path('dersler/yeni/', views.course_create, name='course_create'),
    path('dersler/<int:pk>/', views.course_detail, name='course_detail'),
    path('dersler/<int:pk>/duzenle/', views.course_update, name='course_update'),
    path('dersler/<int:course_pk>/belirtke/yeni/', views.course_spec_table_create, name='course_spec_table_create'),
    path('belirtke/<int:pk>/sil/', views.course_spec_table_delete, name='course_spec_table_delete'),
    path('dersler/<int:course_pk>/sinav/yeni/', views.course_test_form_create, name='course_test_form_create'),
    path('dersler/<int:course_pk>/sinav/<int:tf_pk>/uygula/', views.exam_application_quick, name='exam_application_quick'),
    path('dersler/<int:course_pk>/uygulama/yeni/', views.exam_application_create, name='exam_application_create'),
    path('uygulama/yeni/', views.exam_application_create, name='exam_application_create_general'),
    path('uygulama/<int:pk>/sil/', views.exam_application_delete, name='exam_application_delete'),
    path('dersler/<int:course_pk>/uygulanan-maddeler/', views.course_applied_items, name='course_applied_items'),

    # Faz 12 — Sınav Kağıdı Şablonları ve PDF
    path('sablonlar/', views.exam_template_list, name='exam_template_list'),
    path('sablonlar/yeni/', views.exam_template_create, name='exam_template_create'),
    path('sablonlar/<int:pk>/duzenle/', views.exam_template_update, name='exam_template_update'),
    path('sablonlar/<int:pk>/onizleme/', views.exam_template_preview, name='exam_template_preview'),
    path('formlar/<int:pk>/pdf/', views.test_form_pdf, name='test_form_pdf'),
    path('formlar/<int:pk>/docx/', views.test_form_docx, name='test_form_docx'),
    path('formlar/<int:pk>/AI/auto-balance/', views.test_form_auto_balance, name='test_form_auto_balance'),

    # Faz 13 — Değerlendirme Entegrasyonu
    path('formlar/<int:pk>/cevap-anahtari/', views.test_form_answer_key, name='test_form_answer_key'),
    path('analiz/oturum/<int:session_pk>/cikti-raporu/', views.outcome_performance_report, name='outcome_performance_report'),
]
