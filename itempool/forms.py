from django import forms
from .models import ItemPool, LearningOutcome, Item, ItemChoice, TestForm, Blueprint, SpecificationTable

class ItemPoolForm(forms.ModelForm):
    # ... (existing code unchanged)
    class Meta:
        model = ItemPool
        fields = ['name', 'course', 'semester', 'level', 'status']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Havuz Adı'}),
            'course': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Bağlı Olduğu Ders'}),
            'semester': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Örn: 2024-Güz'}),
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
        fields = ['code', 'description', 'level', 'weight', 'order']
        widgets = {
            'code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'ÖÇ-1'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Çıktı açıklaması'}),
            'level': forms.Select(attrs={'class': 'form-select'}),
            'weight': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '% Ağırlık'}),
            'order': forms.NumberInput(attrs={'class': 'form-control'}),
        }

class ItemForm(forms.ModelForm):
    class Meta:
        model = Item
        fields = ['stem', 'item_type', 'difficulty_intended', 'status']
        widgets = {
            'stem': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Soru kökünü buraya yazın...'}),
            'item_type': forms.Select(attrs={'class': 'form-select'}),
            'difficulty_intended': forms.Select(attrs={'class': 'form-select'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
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
        fields = ['stem', 'difficulty_intended', 'status']
        widgets = {
            'stem': forms.Textarea(attrs={'class': 'form-control', 'rows': 5}),
            'difficulty_intended': forms.Select(attrs={'class': 'form-select'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
        }

ItemChoiceFormSet = forms.inlineformset_factory(
    Item, ItemChoice, form=ItemChoiceForm, 
    extra=5, can_delete=True, min_num=2, validate_min=True
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
