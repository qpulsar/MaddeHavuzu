"""
Admin Dashboard Views for OptikForm.
Custom admin panel with modern dashboard design.
"""
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.db.models import Count, Sum
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.generic import TemplateView, ListView, CreateView, UpdateView, DeleteView, View

from grading.models import (
    UserProfile, UserStatus, FileFormatConfig,
    UploadSession, StudentResult
)


@method_decorator(staff_member_required, name='dispatch')
class AdminDashboardView(TemplateView):
    """Main admin dashboard with statistics."""
    template_name = 'grading/admin/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # User statistics
        context['total_users'] = User.objects.filter(is_staff=False).count()
        context['pending_users'] = UserProfile.objects.filter(status=UserStatus.PENDING).count()
        context['approved_users'] = UserProfile.objects.filter(status=UserStatus.APPROVED).count()
        
        # Upload statistics
        context['total_uploads'] = UploadSession.objects.count()
        context['total_students'] = StudentResult.objects.count()
        
        # Recent pending users
        context['recent_pending'] = UserProfile.objects.filter(
            status=UserStatus.PENDING
        ).select_related('user').order_by('-created_at')[:5]
        
        # Recent uploads
        context['recent_uploads'] = UploadSession.objects.select_related(
            'owner'
        ).order_by('-created_at')[:5]
        
        # File formats
        context['total_formats'] = FileFormatConfig.objects.filter(is_active=True).count()
        
        return context


@method_decorator(staff_member_required, name='dispatch')
class UserManagementView(ListView):
    """User management list view."""
    template_name = 'grading/admin/users.html'
    context_object_name = 'users'
    paginate_by = 20

    def get_queryset(self):
        queryset = UserProfile.objects.select_related('user', 'approved_by').order_by('-created_at')
        
        # Filter by status
        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status)
        
        # Search
        search = self.request.GET.get('q')
        if search:
            queryset = queryset.filter(
                user__username__icontains=search
            ) | queryset.filter(
                user__email__icontains=search
            ) | queryset.filter(
                user__first_name__icontains=search
            ) | queryset.filter(
                user__last_name__icontains=search
            )
        
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['status_choices'] = UserStatus.choices
        context['current_status'] = self.request.GET.get('status', '')
        context['search_query'] = self.request.GET.get('q', '')
        return context


@method_decorator(staff_member_required, name='dispatch')
class UserApproveView(View):
    """Approve a user."""
    def post(self, request, pk):
        profile = get_object_or_404(UserProfile, pk=pk)
        profile.status = UserStatus.APPROVED
        profile.approved_by = request.user
        profile.approved_at = timezone.now()
        profile.save()
        messages.success(request, f'{profile.user.username} kullanıcısı onaylandı.')
        return redirect('admin_users')


@method_decorator(staff_member_required, name='dispatch')
class UserRejectView(View):
    """Reject a user."""
    def post(self, request, pk):
        profile = get_object_or_404(UserProfile, pk=pk)
        profile.status = UserStatus.REJECTED
        profile.save()
        messages.warning(request, f'{profile.user.username} kullanıcısı reddedildi.')
        return redirect('admin_users')


@method_decorator(staff_member_required, name='dispatch')
class UserSuspendView(View):
    """Suspend a user."""
    def post(self, request, pk):
        profile = get_object_or_404(UserProfile, pk=pk)
        profile.status = UserStatus.SUSPENDED
        profile.save()
        messages.warning(request, f'{profile.user.username} kullanıcısı askıya alındı.')
        return redirect('admin_users')


@method_decorator(staff_member_required, name='dispatch')
class FileFormatListView(ListView):
    """File format list view."""
    template_name = 'grading/admin/file_formats.html'
    context_object_name = 'formats'
    queryset = FileFormatConfig.objects.order_by('-is_default', 'name')


@method_decorator(staff_member_required, name='dispatch')
class FileFormatCreateView(CreateView):
    """Create new file format."""
    model = FileFormatConfig
    template_name = 'grading/admin/file_format_form.html'
    fields = [
        'name', 'description', 'format_type', 'delimiter',
        'student_no_start', 'student_no_end',
        'student_name_start', 'student_name_end',
        'answers_start', 'answers_end',
        'has_booklet_field', 'booklet_start', 'booklet_end',
        'key_identifier', 'key_identifier_field',
        'valid_options', 'blank_markers',
        'is_active', 'is_default'
    ]
    success_url = reverse_lazy('admin_formats')

    def form_valid(self, form):
        messages.success(self.request, 'Dosya formatı başarıyla oluşturuldu.')
        return super().form_valid(form)


@method_decorator(staff_member_required, name='dispatch')
class FileFormatEditView(UpdateView):
    """Edit file format."""
    model = FileFormatConfig
    template_name = 'grading/admin/file_format_form.html'
    fields = [
        'name', 'description', 'format_type', 'delimiter',
        'student_no_start', 'student_no_end',
        'student_name_start', 'student_name_end',
        'answers_start', 'answers_end',
        'has_booklet_field', 'booklet_start', 'booklet_end',
        'key_identifier', 'key_identifier_field',
        'valid_options', 'blank_markers',
        'is_active', 'is_default'
    ]
    success_url = reverse_lazy('admin_formats')

    def form_valid(self, form):
        messages.success(self.request, 'Dosya formatı başarıyla güncellendi.')
        return super().form_valid(form)


@method_decorator(staff_member_required, name='dispatch')
class FileFormatDeleteView(DeleteView):
    """Delete file format."""
    model = FileFormatConfig
    success_url = reverse_lazy('admin_formats')

    def form_valid(self, form):
        messages.success(self.request, 'Dosya formatı silindi.')
        return super().form_valid(form)


@method_decorator(staff_member_required, name='dispatch')
class AllUploadsView(ListView):
    """View all uploads from all users."""
    template_name = 'grading/admin/uploads.html'
    context_object_name = 'uploads'
    paginate_by = 20

    def get_queryset(self):
        queryset = UploadSession.objects.select_related('owner', 'file_format').order_by('-created_at')
        
        # Filter by user
        user_id = self.request.GET.get('user')
        if user_id:
            queryset = queryset.filter(owner_id=user_id)
        
        # Filter by status
        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(processing_status=status)
        
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['staff_users'] = User.objects.filter(
            upload_sessions__isnull=False
        ).distinct().order_by('username')
        context['current_user'] = self.request.GET.get('user', '')
        context['current_status'] = self.request.GET.get('status', '')
        return context
