from django.contrib import admin

from optik.models import OptikBatch, OptikRecord, OptikSnapshot, OptikTest


@admin.register(OptikTest)
class OptikTestAdmin(admin.ModelAdmin):
    list_display = ('test_id', 'course_code', 'exam_type', 'owner', 'is_approved', 'deleted', 'created_at')
    list_filter = ('is_approved', 'deleted', 'academic_year', 'semester')
    search_fields = ('test_id', 'course_code', 'course_name')


@admin.register(OptikBatch)
class OptikBatchAdmin(admin.ModelAdmin):
    list_display = ('batch_id', 'test', 'status', 'created_at')
    list_filter = ('status',)
    search_fields = ('batch_id', 'test__test_id', 'test__course_code')


@admin.register(OptikRecord)
class OptikRecordAdmin(admin.ModelAdmin):
    list_display = ('record_id', 'batch', 'student_no', 'booklet', 'created_at')
    search_fields = ('record_id', 'student_no', 'batch__batch_id')


@admin.register(OptikSnapshot)
class OptikSnapshotAdmin(admin.ModelAdmin):
    list_display = ('batch', 'version', 'created_at')
