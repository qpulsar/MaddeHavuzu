from django.urls import path
from . import views

app_name = 'itempool'

urlpatterns = [
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
]
