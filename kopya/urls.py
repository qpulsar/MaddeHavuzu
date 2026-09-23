"""
Kopya Analizi URL'leri (kaynak: cheating/routes.py, prefix /cheating → /kopya).

`source_id`: optik batch_id ("batch_xxxxxxxx") veya Excel yüklemesi ("xl_<uid>").
Sabit yollar (upload, template) değişken yoldan önce gelir.
"""
from django.urls import path

from kopya import views

app_name = 'kopya'

urlpatterns = [
    path('', views.index, name='index'),
    path('upload/', views.upload, name='excel_upload'),
    path('upload/analyze/', views.upload_analyze, name='excel_analyze'),
    path('template.xlsx', views.template_xlsx, name='excel_template'),
    path('<str:source_id>/', views.dashboard, name='panel'),
    path('<str:source_id>/pair/<str:copier>/<str:source>/', views.pair_detail, name='pair_detail'),
]
