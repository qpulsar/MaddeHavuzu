from django.contrib import admin

from kopya.models import KopyaAnalysis, KopyaUpload


@admin.register(KopyaUpload)
class KopyaUploadAdmin(admin.ModelAdmin):
    list_display = ('upload_id', 'original_filename', 'owner', 'created_at')
    search_fields = ('upload_id', 'original_filename')


@admin.register(KopyaAnalysis)
class KopyaAnalysisAdmin(admin.ModelAdmin):
    list_display = ('source_id', 'alpha', 'input_hash', 'computed_at', 'duration_seconds')
    exclude = ('result',)
