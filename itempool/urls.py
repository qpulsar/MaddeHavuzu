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

    # AI Öneri Rotaları
    path('items/<int:pk>/AI/suggest-outcomes/', views.item_suggest_outcomes, name='item_suggest_outcomes'),
    path('items/<int:pk>/AI/assign-outcome/<int:outcome_id>/', views.item_assign_outcome, name='item_assign_outcome'),

    # Madde Detay Düzenleme (HTMX)
    path('items/instance/<int:pk>/edit/<str:section>/', views.item_detail_edit, name='item_detail_edit'),
    path('items/instance/<int:pk>/save/<str:section>/', views.item_detail_save, name='item_detail_save'),

    # Test Formu Rotaları
    path('<int:pool_id>/formlar/yeni/', views.test_form_create, name='test_form_create'),
    path('formlar/<int:pk>/', views.test_form_detail, name='test_form_detail'),
    path('formlar/<int:pk>/maddeler/duzenle/', views.test_form_edit_items, name='test_form_edit_items'),
    path('formlar/<int:pk>/wizard/blueprint/', views.test_form_wizard_blueprint, name='test_form_wizard_blueprint'),
    path('formlar/<int:pk>/maddeler/ekle/<int:instance_id>/', views.test_form_add_item, name='test_form_add_item'),
    path('formlar/<int:pk>/maddeler/cikar/<int:item_id>/', views.test_form_remove_item, name='test_form_remove_item'),
    path('blueprints/<int:pk>/klonla/', views.blueprint_clone, name='blueprint_clone'),
    path('analiz/yukle/', views.analysis_upload, name='analysis_upload'),
    path('analiz/get-forms/', views.analysis_get_forms, name='analysis_get_forms'),

    # Faz 11 — Öğrenci Grubu ve Sınav Uygulama Rotaları
    path('gruplar/', views.student_group_list, name='student_group_list'),
    path('gruplar/yeni/', views.student_group_create, name='student_group_create'),
    path('gruplar/<int:pk>/', views.student_group_detail, name='student_group_detail'),
    path('gruplar/<int:group_pk>/uygulama/yeni/', views.exam_application_create, name='exam_application_create'),
    path('uygulama/yeni/', views.exam_application_create, name='exam_application_create_general'),
    path('uygulama/<int:pk>/sil/', views.exam_application_delete, name='exam_application_delete'),
    path('gruplar/<int:group_pk>/uygulanan-maddeler/', views.group_applied_items, name='group_applied_items'),

    # Faz 12 — Sınav Kağıdı Şablonları ve PDF
    path('sablonlar/', views.exam_template_list, name='exam_template_list'),
    path('sablonlar/yeni/', views.exam_template_create, name='exam_template_create'),
    path('sablonlar/<int:pk>/duzenle/', views.exam_template_update, name='exam_template_update'),
    path('sablonlar/<int:pk>/onizleme/', views.exam_template_preview, name='exam_template_preview'),
    path('formlar/<int:pk>/pdf/', views.test_form_pdf, name='test_form_pdf'),

    # Faz 13 — Değerlendirme Entegrasyonu
    path('formlar/<int:pk>/cevap-anahtari/', views.test_form_answer_key, name='test_form_answer_key'),
    path('analiz/oturum/<int:session_pk>/cikti-raporu/', views.outcome_performance_report, name='outcome_performance_report'),
]
