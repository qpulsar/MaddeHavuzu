from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from django.utils import timezone
from django.utils.html import format_html
from django.contrib import messages

from grading.models import (
    UserProfile, UserStatus, FileFormatConfig,
    UploadSession, StudentResult, ParsingError
)


class UserProfileInline(admin.StackedInline):
    """Inline admin for UserProfile in User admin."""
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'Profil'
    fk_name = 'user'
    readonly_fields = ('approved_by', 'approved_at', 'created_at', 'updated_at')


class UserAdmin(BaseUserAdmin):
    """Extended User admin with profile inline."""
    inlines = (UserProfileInline,)
    list_display = ('username', 'email', 'first_name', 'last_name', 'get_status', 'is_staff', 'date_joined')
    list_filter = BaseUserAdmin.list_filter + ('profile__status',)
    
    def get_status(self, obj):
        if hasattr(obj, 'profile'):
            status = obj.profile.status
            colors = {
                UserStatus.PENDING: 'orange',
                UserStatus.APPROVED: 'green',
                UserStatus.REJECTED: 'red',
                UserStatus.SUSPENDED: 'gray',
            }
            return format_html(
                '<span style="color: {}; font-weight: bold;">{}</span>',
                colors.get(status, 'black'),
                obj.profile.get_status_display()
            )
        return '-'
    get_status.short_description = 'Durum'


# Re-register User with new admin
admin.site.unregister(User)
admin.site.register(User, UserAdmin)


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    """Admin for UserProfile with approval actions."""
    list_display = ('user', 'status', 'approved_by', 'approved_at', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('user__username', 'user__email', 'user__first_name', 'user__last_name')
    readonly_fields = ('approved_by', 'approved_at', 'created_at', 'updated_at')
    actions = ['approve_users', 'reject_users', 'suspend_users']
    
    def approve_users(self, request, queryset):
        """Approve selected users."""
        count = 0
        for profile in queryset:
            if profile.status != UserStatus.APPROVED:
                profile.status = UserStatus.APPROVED
                profile.approved_by = request.user
                profile.approved_at = timezone.now()
                profile.save()
                count += 1
        self.message_user(request, f'{count} kullanıcı onaylandı.', messages.SUCCESS)
    approve_users.short_description = 'Seçili kullanıcıları onayla'
    
    def reject_users(self, request, queryset):
        """Reject selected users."""
        count = queryset.exclude(status=UserStatus.REJECTED).update(status=UserStatus.REJECTED)
        self.message_user(request, f'{count} kullanıcı reddedildi.', messages.WARNING)
    reject_users.short_description = 'Seçili kullanıcıları reddet'
    
    def suspend_users(self, request, queryset):
        """Suspend selected users."""
        count = queryset.exclude(status=UserStatus.SUSPENDED).update(status=UserStatus.SUSPENDED)
        self.message_user(request, f'{count} kullanıcı askıya alındı.', messages.WARNING)
    suspend_users.short_description = 'Seçili kullanıcıları askıya al'


@admin.register(FileFormatConfig)
class FileFormatConfigAdmin(admin.ModelAdmin):
    """Admin for file format configuration."""
    list_display = ('name', 'format_type', 'is_active', 'is_default', 'created_at')
    list_filter = ('format_type', 'is_active', 'is_default')
    search_fields = ('name', 'description')
    
    fieldsets = (
        ('Genel Bilgiler', {
            'fields': ('name', 'description', 'format_type', 'delimiter', 'is_active', 'is_default')
        }),
        ('Alan Pozisyonları (Sabit Genişlik)', {
            'fields': (
                ('student_no_start', 'student_no_end'),
                ('student_name_start', 'student_name_end'),
                ('answers_start', 'answers_end'),
            ),
            'classes': ('collapse',),
        }),
        ('Kitapçık Alanı (Opsiyonel)', {
            'fields': ('has_booklet_field', ('booklet_start', 'booklet_end')),
            'classes': ('collapse',),
        }),
        ('Anahtar ve Değerlendirme Ayarları', {
            'fields': ('key_identifier', 'key_identifier_field', 'valid_options', 'blank_markers'),
        }),
    )


@admin.register(UploadSession)
class UploadSessionAdmin(admin.ModelAdmin):
    """Admin for upload sessions."""
    list_display = ('original_filename', 'owner', 'processing_status', 'question_count', 'student_count', 'error_count', 'created_at')
    list_filter = ('processing_status', 'created_at', 'owner')
    search_fields = ('original_filename', 'owner__username')
    readonly_fields = ('owner', 'original_filename', 'uploaded_file', 'file_format', 'created_at', 'processed_at',
                       'processing_status', 'question_count', 'student_count', 'error_count', 'error_summary')
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False


@admin.register(StudentResult)
class StudentResultAdmin(admin.ModelAdmin):
    """Admin for student results."""
    list_display = ('student_name', 'student_no', 'correct_count', 'wrong_count', 'blank_count', 'invalid_count', 'score', 'upload_session')
    list_filter = ('upload_session',)
    search_fields = ('student_name', 'student_no')
    readonly_fields = ('upload_session', 'student_no', 'student_name', 'booklet', 'answers_raw',
                       'row_number_in_file', 'correct_count', 'wrong_count', 'blank_count',
                       'invalid_count', 'score', 'detailed_results')
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False


@admin.register(ParsingError)
class ParsingErrorAdmin(admin.ModelAdmin):
    """Admin for parsing errors."""
    list_display = ('upload_session', 'row_number', 'message')
    list_filter = ('upload_session',)
    readonly_fields = ('upload_session', 'row_number', 'raw_line', 'message', 'created_at')
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False


# Customize admin site
admin.site.site_header = 'OptikForm Yönetim Paneli'
admin.site.site_title = 'OptikForm Admin'
admin.site.index_title = 'Yönetim'
