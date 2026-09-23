"""
Optik Okuma URL'leri (kaynak: omr_analysis routes, prefix /omr → /optik).

Yol yapısı kaynakla aynı tutuldu; her route'un kaynaktaki karşılığı view
modülündeki docstring'de yazılıdır.
"""
from django.urls import path

from optik.views import answer_key, records, scoring, testler, upload

app_name = 'optik'

urlpatterns = [
    # Ana sayfa + test (sihirbaz 1. adım)
    path('', testler.index, name='index'),
    path('test/new/', testler.test_new, name='test_new'),
    path('test/create/', testler.test_create, name='test_create'),
    path('test/<str:test_id>/', testler.test_detail, name='test_detail'),
    path('test/<str:test_id>/edit/', testler.test_edit, name='test_edit'),
    path('test/<str:test_id>/remove-approval/', testler.test_remove_approval, name='test_remove_approval'),

    # Form yükleme (2. adım) + ilerleme
    path('test/<str:test_id>/upload-forms/', upload.upload_forms, name='upload_forms'),
    path('batch/<str:batch_id>/progress/', upload.progress, name='progress'),
    path('batch/<str:batch_id>/progress-api/', upload.progress_api, name='progress_api'),

    # Cevap anahtarı + madde puanları (3. adım)
    path('test/<str:test_id>/answer-key/', answer_key.answer_key, name='answer_key'),
    path('test/<str:test_id>/save-answer-key/', answer_key.save_answer_key, name='save_answer_key'),
    path('test/<str:test_id>/save-all-answer-keys/', answer_key.save_all_answer_keys, name='save_all_answer_keys'),
    path('test/<str:test_id>/auto-save-answer-keys/', answer_key.auto_save_answer_keys, name='auto_save_answer_keys'),
    path('test/<str:test_id>/save-item-points/', answer_key.save_item_points, name='save_item_points'),
    path('test/<str:test_id>/save-detailed-points/', answer_key.save_detailed_points, name='save_detailed_points'),
    path('test/<str:test_id>/save-booklet-mapping/', answer_key.save_booklet_mapping, name='save_booklet_mapping'),
    path('test/<str:test_id>/answer-key/upload/', answer_key.answer_key_upload, name='answer_key_upload'),

    # Kayıtlar (4. adım)
    path('test/<str:test_id>/records/', records.test_records, name='records'),
    path('batch/<str:batch_id>/', records.batch_detail, name='batch_detail'),
    path('batch/<str:batch_id>/records/delete-selected/', records.delete_selected, name='records_delete_selected'),
    path('batch/<str:batch_id>/record/<str:record_id>/', records.record_detail, name='record_detail'),
    path('batch/<str:batch_id>/record/<str:record_id>/delete/', records.record_delete, name='record_delete'),
    path('batch/<str:batch_id>/record/<str:record_id>/overlay/', records.record_overlay, name='record_overlay'),
    path('batch/<str:batch_id>/record/<str:record_id>/image/', records.record_image, name='record_image'),
    path('batch/<str:batch_id>/record/<str:record_id>/edit/', records.record_edit, name='record_edit'),
    path('batch/<str:batch_id>/record/<str:record_id>/save/', records.record_save, name='record_save'),

    # Puanlama (5. adım), dışa aktarma, onay
    path('test/<str:test_id>/scoring/', scoring.test_scoring, name='scoring'),
    path('batch/<str:batch_id>/do-scoring/', scoring.do_scoring, name='do_scoring'),
    path('batch/<str:batch_id>/open-scoring/', scoring.open_scoring, name='open_scoring'),
    path('batch/<str:batch_id>/save-open-scores/', scoring.save_open_scores, name='save_open_scores'),
    path('batch/<str:batch_id>/score/', scoring.batch_score_page, name='batch_score'),
    path('batch/<str:batch_id>/scores/', scoring.batch_scores, name='batch_scores'),
    path('batch/<str:batch_id>/score/<str:student_no>/', scoring.student_score, name='student_score'),
    path('batch/<str:batch_id>/export-scores/', scoring.export_scores, name='export_scores'),
    path('batch/<str:batch_id>/approve-form/', scoring.approve_form, name='approve_form'),
    path('batch/<str:batch_id>/approve/', scoring.approve, name='approve'),
    path('batch/<str:batch_id>/snapshot/<str:version>/', scoring.snapshot_detail, name='snapshot_detail'),
]
