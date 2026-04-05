from django.db import models
from django.contrib.auth.models import User
from .pool import ItemPool, LearningOutcome
from .item import ItemInstance

class TestForm(models.Model):
    """
    Birden fazla havuzdan seçilen maddelerle oluşturulan sınav formu.
    """
    class Status(models.TextChoices):
        DRAFT = 'DRAFT', 'Taslak'
        ACTIVE = 'ACTIVE', 'Aktif'
        APPLIED = 'APPLIED', 'Uygulandı'
        ARCHIVED = 'ARCHIVED', 'Arşivlendi'

    # Derse bağlantı (nullable — bağımsız form oluşturulabilir)
    course = models.ForeignKey(
        'itempool.Course',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='test_forms',
        verbose_name='Ders'
    )
    # Soru çekilecek havuzlar
    pools = models.ManyToManyField(
        ItemPool,
        blank=True,
        related_name='test_forms',
        verbose_name='Madde Havuzları'
    )
    name = models.CharField(max_length=255, verbose_name='Form Adı')
    description = models.TextField(null=True, blank=True, verbose_name='Açıklama')

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
        verbose_name='Durum'
    )
    
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, verbose_name='Oluşturan')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Oluşturma kuralı (JSON olarak saklanabilir veya Blueprint FK olabilir)
    generation_metadata = models.JSONField(default=dict, blank=True, verbose_name='Oluşturma Kuralları')

    class Meta:
        verbose_name = 'Test Formu'
        verbose_name_plural = 'Test Formları'
        ordering = ['-created_at']

    def __str__(self):
        return self.name

class FormItem(models.Model):
    """
    Test formundaki bir madde ve o formdaki özellikleri (puan, sıra vb).
    """
    form = models.ForeignKey(
        TestForm,
        on_delete=models.CASCADE,
        related_name='form_items',
        verbose_name='Form'
    )
    item_instance = models.ForeignKey(
        ItemInstance,
        on_delete=models.CASCADE,
        related_name='form_usage',
        verbose_name='Madde'
    )
    order = models.PositiveIntegerField(verbose_name='Soru Sırası')
    points = models.DecimalField(max_digits=5, decimal_places=2, default=1.0, verbose_name='Puan')
    
    # Sınav formundaki şık düzenlemeleri (shuffling/balancıng sonucu)
    # Format: [{"label": "A", "text": "...", "is_correct": bool}, ...]
    choice_overrides = models.JSONField(null=True, blank=True, verbose_name='Şık Düzenlemeleri')

    class Meta:
        verbose_name = 'Form Maddesi'
        verbose_name_plural = 'Form Maddeleri'
        ordering = ['order']
        unique_together = ('form', 'item_instance')

    def __str__(self):
        return f"{self.form.name} - Soru {self.order}"

class Blueprint(models.Model):
    """
    Sınavın öğrenme çıktılarına göre dağılım şablonu.
    """
    name = models.CharField(max_length=255, verbose_name='Blueprint Adı')
    pool = models.ForeignKey(ItemPool, on_delete=models.CASCADE, related_name='blueprints', verbose_name='Havuz')
    
    # Örn: {"outcome_id": adet, ...}
    distribution_json = models.JSONField(verbose_name='Çıktı Dağılımı')
    total_items = models.PositiveIntegerField(verbose_name='Toplam Soru Sayısı')
    
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, verbose_name='Oluşturan')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Blueprint / Şablon'
        verbose_name_plural = 'Blueprints / Şablonlar'

    def __str__(self):
        return self.name

class SpecificationTable(models.Model):
    """
    Öğrenme çıktıları ile konuların kesiştiği belirtke tablosu.
    """
    pool = models.ForeignKey(ItemPool, on_delete=models.CASCADE, related_name='spec_tables', verbose_name='Havuz')
    name = models.CharField(max_length=255, verbose_name='Tablo Adı')
    
    # Matris verisi: rows_json = [{"outcome_id": ID, "topics": {"topic_name": weight, ...}}, ...]
    rows_json = models.JSONField(verbose_name='Tablo Verisi')
    
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, verbose_name='Oluşturan')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Belirtke Tablosu'
        verbose_name_plural = 'Belirtke Tabloları'

    def __str__(self):
        return self.name
