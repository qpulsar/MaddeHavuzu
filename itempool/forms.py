from django import forms
from .models import ItemPool, LearningOutcome, Item, ItemChoice, TestForm, Blueprint, SpecificationTable, Course, CourseSpecTable, ExamApplication, ExamTemplate

class ItemPoolForm(forms.ModelForm):
    class Meta:
        model = ItemPool
        fields = ['name', 'description', 'level', 'status']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Havuz Adı'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Hangi konu veya aşanlara ait olduğunu açıklayın...'}),
            'level': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Örn: Lisans 1'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
        }


class LearningOutcomeForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        self.pool = kwargs.pop('pool', None)
        super().__init__(*args, **kwargs)

    def clean_code(self):
        code = self.cleaned_data.get('code')
        if self.pool and LearningOutcome.objects.filter(pool=self.pool, code=code).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("Bu kod bu havuzda zaten kullanılıyor.")
        return code

    class Meta:
        model = LearningOutcome
        fields = ['code', 'description', 'level', 'order']
        widgets = {
            'code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'ÖÇ-1'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Çıktı açıklaması'}),
            'level': forms.Select(attrs={'class': 'form-select'}),
            'order': forms.NumberInput(attrs={'class': 'form-control'}),
        }

class ItemForm(forms.ModelForm):
    class Meta:
        model = Item
        fields = ['stem', 'item_type', 'max_choices', 'difficulty_intended', 'status', 'expected_answer', 'scoring_rubric']
        widgets = {
            'stem': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Soru kökünü buraya yazın...'}),
            'item_type': forms.Select(attrs={'class': 'form-select', 'id': 'id_item_type'}),
            'max_choices': forms.NumberInput(attrs={'class': 'form-control', 'min': 2, 'max': 10}),
            'difficulty_intended': forms.Select(attrs={'class': 'form-select'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'expected_answer': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Kabul edilebilir kısa cevap(lar)...'}),
            'scoring_rubric': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Puanlama kriterleri, tam cevap, kısmi cevap...'}),
        }

class ItemChoiceForm(forms.ModelForm):
    class Meta:
        model = ItemChoice
        fields = ['label', 'text', 'is_correct', 'order']
        widgets = {
            'label': forms.TextInput(attrs={'class': 'form-control form-control-sm', 'placeholder': 'A'}),
            'text': forms.TextInput(attrs={'class': 'form-control form-control-sm', 'placeholder': 'Seçenek metni'}),
            'is_correct': forms.CheckboxInput(attrs={'class': 'form-check-input mt-2'}),
            'order': forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'style': 'width: 50px;'}),
        }

class ItemDetailEditForm(forms.ModelForm):
    class Meta:
        model = Item
        fields = ['stem', 'difficulty_intended', 'status', 'max_choices', 'expected_answer', 'scoring_rubric']
        widgets = {
            'stem': forms.Textarea(attrs={'class': 'form-control', 'rows': 5}),
            'difficulty_intended': forms.Select(attrs={'class': 'form-select'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'max_choices': forms.NumberInput(attrs={'class': 'form-control', 'min': 2, 'max': 10}),
            'expected_answer': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'scoring_rubric': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
        }

ItemChoiceFormSet = forms.inlineformset_factory(
    Item, ItemChoice, form=ItemChoiceForm,
    extra=4, can_delete=True, min_num=2, validate_min=True,
    max_num=10, validate_max=True
)

class TestFormForm(forms.ModelForm):
    METHOD_CHOICES = [
        ('MANUAL', 'Manuel Seçim (Tek tek ekle)'),
        ('BLUEPRINT', 'Blueprint (Dağılım şablonuna göre otomatik)'),
        ('SPEC_TABLE', 'Belirtke Tablosu (Konu matrisine göre otomatik)'),
    ]
    creation_method = forms.ChoiceField(
        choices=METHOD_CHOICES, 
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'}), 
        initial='MANUAL',
        label="Oluşturma Yöntemi"
    )

    class Meta:
        model = TestForm
        fields = ['name', 'description']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Örn: 2024 Vize Formu'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Form açıklaması...'}),
        }

class BlueprintForm(forms.ModelForm):
    class Meta:
        model = Blueprint
        fields = ['name', 'total_items']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'total_items': forms.NumberInput(attrs={'class': 'form-control'}),
        }

class SpecificationTableForm(forms.ModelForm):
    class Meta:
        model = SpecificationTable
        fields = ['name']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
        }


class CourseForm(forms.ModelForm):
    class Meta:
        model = Course
        fields = ['name', 'code', 'semester', 'description', 'pools']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Örn: Eğitim Psikolojisi'}),
            'code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Örn: EPD 201'}),
            'semester': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Örn: 2026-Güz'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Ders hakkında notlar...'}),
            'pools': forms.CheckboxSelectMultiple(),
        }


class CourseSpecTableForm(forms.ModelForm):
    class Meta:
        model = CourseSpecTable
        fields = ['name']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Örn: Vize Belirtke Tablosu'}),
        }


class TestFormCreateForm(forms.ModelForm):
    """Derse ait sınav formu oluşturma formu."""
    DIFFICULTY_CHOICES = [
        ('MIXED', 'Karışık (Hepsi)'),
        ('EASY', 'Kolay Ağırlıklı'),
        ('MEDIUM', 'Orta Ağırlıklı'),
        ('HARD', 'Zor Ağırlıklı'),
    ]

    # Otomatik seçim kriterleri (ek alanlar)
    difficulty = forms.ChoiceField(
        choices=DIFFICULTY_CHOICES,
        initial='MIXED',
        required=False,
        label='Zorluk Dağılımı',
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    n_mcq = forms.IntegerField(min_value=0, initial=0, required=False, label='Çoktan Seçmeli',
                               widget=forms.NumberInput(attrs={'class': 'form-control', 'min': 0}))
    n_tf = forms.IntegerField(min_value=0, initial=0, required=False, label='Doğru/Yanlış',
                              widget=forms.NumberInput(attrs={'class': 'form-control', 'min': 0}))
    n_short = forms.IntegerField(min_value=0, initial=0, required=False, label='Kısa Cevaplı',
                                 widget=forms.NumberInput(attrs={'class': 'form-control', 'min': 0}))
    n_open = forms.IntegerField(min_value=0, initial=0, required=False, label='Açık Uçlu',
                                widget=forms.NumberInput(attrs={'class': 'form-control', 'min': 0}))
    excluded_forms = forms.ModelMultipleChoiceField(
        queryset=TestForm.objects.none(),
        required=False,
        label='Soru Benzerliği İstenmeyen Sınavlar',
        widget=forms.CheckboxSelectMultiple(),
        help_text='Seçili sınavlardaki sorular otomatik seçimde dışarıda bırakılır.'
    )

    class Meta:
        model = TestForm
        fields = ['name', 'description', 'pools']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Örn: 2026-Güz Vize Sınavı'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Sınav hakkında notlar...'}),
            'pools': forms.CheckboxSelectMultiple(),
        }

    def __init__(self, *args, course=None, **kwargs):
        super().__init__(*args, **kwargs)
        if course:
            self.fields['pools'].queryset = course.pools.all()
            self.fields['pools'].initial = course.pools.all()
            self.fields['excluded_forms'].queryset = TestForm.objects.filter(
                course=course
            ).order_by('-created_at')


class ExamApplicationForm(forms.ModelForm):
    class Meta:
        model = ExamApplication
        fields = ['test_form', 'course', 'applied_at', 'notes']
        widgets = {
            'test_form': forms.Select(attrs={'class': 'form-select'}),
            'course': forms.Select(attrs={'class': 'form-select'}),
            'applied_at': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }


class ExamTemplateForm(forms.ModelForm):
    docx_header_file = forms.FileField(
        required=False,
        label='Word Başlık Şablonu (.docx)',
        help_text='Mevcut başlık alanlarını geçersiz kılar. Logo ve tablo içeren bir Word dosyası yükleyebilirsiniz.',
        widget=forms.FileInput(attrs={'class': 'form-control', 'accept': '.docx'})
    )

    class Meta:
        model = ExamTemplate
        fields = [
            'name', 'is_default', 'page_size', 'column_count', 'column_divider',
            'margin_top', 'margin_bottom', 'margin_left', 'margin_right',
            'font_family', 'font_size', 'question_spacing', 'choice_spacing', 'choice_layout',
            'header_left', 'header_center', 'header_right', 'show_header_line',
            'footer_left', 'footer_center', 'footer_right', 'show_footer_line',
            'show_student_info_box', 'show_question_points',
            'header_html', 'footer_html',
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'is_default': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'page_size': forms.Select(attrs={'class': 'form-select'}),
            'column_count': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'max': 3}),
            'column_divider': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'margin_top': forms.NumberInput(attrs={'class': 'form-control', 'min': 5, 'max': 50}),
            'margin_bottom': forms.NumberInput(attrs={'class': 'form-control', 'min': 5, 'max': 50}),
            'margin_left': forms.NumberInput(attrs={'class': 'form-control', 'min': 5, 'max': 50}),
            'margin_right': forms.NumberInput(attrs={'class': 'form-control', 'min': 5, 'max': 50}),
            'font_family': forms.Select(attrs={'class': 'form-select'}),
            'font_size': forms.NumberInput(attrs={'class': 'form-control', 'min': 8, 'max': 16}),
            'question_spacing': forms.NumberInput(attrs={'class': 'form-control', 'min': 4, 'max': 30}),
            'choice_spacing': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'max': 20}),
            'choice_layout': forms.Select(attrs={'class': 'form-select'}),
            'header_left': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '{course}'}),
            'header_center': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '{form_name}'}),
            'header_right': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Tarih: {date}'}),
            'show_header_line': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'footer_left': forms.TextInput(attrs={'class': 'form-control'}),
            'footer_center': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '{page} / {total_pages}'}),
            'footer_right': forms.TextInput(attrs={'class': 'form-control'}),
            'show_footer_line': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'show_student_info_box': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'show_question_points': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'header_html': forms.Textarea(attrs={'class': 'form-control', 'rows': 5}),
            'footer_html': forms.Textarea(attrs={'class': 'form-control', 'rows': 5}),
        }
