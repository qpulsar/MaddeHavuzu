from django.contrib import admin
from .models import (
    ItemPool, LearningOutcome, Item, ItemChoice, ItemInstance,
    ImportBatch, DraftItem, OutcomeSuggestion, ItemAnalysisResult,
    TestForm, FormItem, Blueprint, SpecificationTable,
    Course, CourseSpecTable, ExamApplication, AIPrompt
)


class LearningOutcomeInline(admin.TabularInline):
    model = LearningOutcome
    extra = 1


@admin.register(ItemPool)
class ItemPoolAdmin(admin.ModelAdmin):
    list_display = ('name', 'level', 'status', 'owner', 'created_at')
    list_filter = ('level', 'status')
    search_fields = ('name', 'description')
    inlines = [LearningOutcomeInline]
    date_hierarchy = 'created_at'


class ItemChoiceInline(admin.TabularInline):
    model = ItemChoice
    extra = 4


@admin.register(ItemAnalysisResult)
class ItemAnalysisResultAdmin(admin.ModelAdmin):
    list_display = ('id', 'item_instance', 'difficulty_p', 'discrimination_r', 'risk_score', 'flagged')
    list_filter = ('flagged',)


class FormItemInline(admin.TabularInline):
    model = FormItem
    extra = 1


@admin.register(TestForm)
class TestFormAdmin(admin.ModelAdmin):
    list_display = ('name', 'course', 'status', 'created_by', 'created_at')
    list_filter = ('status', 'course')
    search_fields = ('name',)
    inlines = [FormItemInline]


class CourseSpecTableInline(admin.TabularInline):
    model = CourseSpecTable
    extra = 0


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'semester', 'created_by', 'created_at')
    list_filter = ('semester',)
    search_fields = ('name', 'code')
    filter_horizontal = ('pools',)
    inlines = [CourseSpecTableInline]


@admin.register(ExamApplication)
class ExamApplicationAdmin(admin.ModelAdmin):
    list_display = ('test_form', 'course', 'applied_at', 'created_by')
    list_filter = ('course',)


@admin.register(Blueprint)
class BlueprintAdmin(admin.ModelAdmin):
    list_display = ('name', 'pool', 'total_items', 'created_by')


@admin.register(SpecificationTable)
class SpecificationTableAdmin(admin.ModelAdmin):
    list_display = ('name', 'pool', 'created_by')


@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    list_display = ('id', 'stem_short', 'item_type', 'difficulty_intended', 'status', 'author', 'version')
    list_filter = ('item_type', 'difficulty_intended', 'status')
    search_fields = ('stem',)
    inlines = [ItemChoiceInline]
    date_hierarchy = 'created_at'

    def stem_short(self, obj):
        return obj.stem[:50] + '...' if len(obj.stem) > 50 else obj.stem
    stem_short.short_description = 'Madde Kökü'


@admin.register(ItemInstance)
class ItemInstanceAdmin(admin.ModelAdmin):
    list_display = ('id', 'pool', 'item_id', 'get_outcomes', 'is_fork', 'added_by', 'added_at')
    list_filter = ('pool', 'is_fork')
    search_fields = ('item__stem', 'pool__name')
    date_hierarchy = 'added_at'

    def item_id(self, obj):
        return f"Madde #{obj.item.id}"
    item_id.short_description = 'Madde'

    def get_outcomes(self, obj):
        return ", ".join([o.code for o in obj.learning_outcomes.all()])
    get_outcomes.short_description = 'Öğrenme Çıktıları'

@admin.register(AIPrompt)
class AIPromptAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'is_active', 'updated_at')
    list_filter = ('is_active',)
    search_fields = ('name', 'slug', 'description', 'template')
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        (None, {
            'fields': ('name', 'slug', 'description', 'is_active')
        }),
        ('Prompt Detayları', {
            'fields': ('system_instruction', 'template'),
            'description': 'Şablonda kullanılabilecek değişkenler (örnek): {stem}, {choices}, {outcomes_text}'
        }),
        ('Zaman Bilgileri', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
