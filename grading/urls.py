"""
URL configuration for grading app.
"""
from django.urls import path
from grading.views.auth import (
    LandingView, RegisterView, CustomLoginView, CustomLogoutView, FeaturesView
)
from grading.views.dashboard import DashboardView, NewUploadView, UploadDetailView, DownloadExcelView, UploadSessionDeleteView, UploadStatisticsView, UpdatePenaltyView, KR20StatisticsView, AlphaStatisticsView
from grading.views.admin_dashboard import (
    AdminDashboardView, UserManagementView, UserApproveView, UserRejectView, UserSuspendView,
    FileFormatListView, FileFormatCreateView, FileFormatEditView, FileFormatDeleteView,
    AllUploadsView
)
from grading.views.profile import ProfileView, ChangePasswordView, SetThemeView
from grading.views.analysis import CheatingAnalysisView

urlpatterns = [
    # Landing
    path('', LandingView.as_view(), name='landing'),
    path('ozellikler/', FeaturesView.as_view(), name='features'),
    
    # Authentication
    path('kayit/', RegisterView.as_view(), name='register'),
    path('giris/', CustomLoginView.as_view(), name='login'),
    path('cikis/', CustomLogoutView.as_view(), name='logout'),
    
    # Profile
    path('profil/', ProfileView.as_view(), name='profile'),
    path('profil/sifre-degistir/', ChangePasswordView.as_view(), name='change_password'),
    path('profil/tema/', SetThemeView.as_view(), name='set_theme'),
    
    # Dashboard
    path('panel/', DashboardView.as_view(), name='dashboard'),
    
    # Upload
    path('yuklemeler/yeni/', NewUploadView.as_view(), name='new_upload'),
    path('yuklemeler/<int:pk>/', UploadDetailView.as_view(), name='upload_detail'),
    path('yuklemeler/<int:pk>/excel/', DownloadExcelView.as_view(), name='download_excel'),
    path('yuklemeler/<int:pk>/sil/', UploadSessionDeleteView.as_view(), name='upload_delete'),
    path('yuklemeler/<int:pk>/istatistik/', UploadStatisticsView.as_view(), name='upload_stats'),
    path('yuklemeler/<int:pk>/kr20/', KR20StatisticsView.as_view(), name='upload_kr20'),
    path('yuklemeler/<int:pk>/alpha/', AlphaStatisticsView.as_view(), name='upload_alpha'),
    path('yuklemeler/<int:pk>/oran-guncelle/', UpdatePenaltyView.as_view(), name='update_penalty'),
    
    # Admin Dashboard
    path('yonetim/', AdminDashboardView.as_view(), name='admin_dashboard'),
    path('yonetim/kullanicilar/', UserManagementView.as_view(), name='admin_users'),
    path('yonetim/kullanicilar/<int:pk>/onayla/', UserApproveView.as_view(), name='admin_user_approve'),
    path('yonetim/kullanicilar/<int:pk>/reddet/', UserRejectView.as_view(), name='admin_user_reject'),
    path('yonetim/kullanicilar/<int:pk>/askiya-al/', UserSuspendView.as_view(), name='admin_user_suspend'),
    path('yonetim/formatlar/', FileFormatListView.as_view(), name='admin_formats'),
    path('yonetim/formatlar/yeni/', FileFormatCreateView.as_view(), name='admin_format_create'),
    path('yonetim/formatlar/<int:pk>/duzenle/', FileFormatEditView.as_view(), name='admin_format_edit'),
    path('yonetim/formatlar/<int:pk>/sil/', FileFormatDeleteView.as_view(), name='admin_format_delete'),
    path('yonetim/formatlar/<int:pk>/sil/', FileFormatDeleteView.as_view(), name='admin_format_delete'),
    path('yonetim/yuklemeler/', AllUploadsView.as_view(), name='admin_uploads'),
    
    # Cheating Analysis
    path('yuklemeler/<int:pk>/kopya-analizi/', CheatingAnalysisView.as_view(), name='cheating_analysis'),
]

