from django.db import models
from django.contrib.auth.models import User
from .pool import ItemPool

class ImportBatch(models.Model):
    """
    Toplu madde yükleme işlemini temsil eder.
    """
    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Beklemede'
        PROCESSING = 'PROCESSING', 'İşleniyor'
        COMPLETED = 'COMPLETED', 'Tamamlandı'
        FAILED = 'FAILED', 'Hata Oluştu'

    pool = models.ForeignKey(
        ItemPool,
        on_delete=models.CASCADE,
        related_name='import_batches',
        verbose_name='Havuz'
    )
    original_filename = models.CharField(
        max_length=255,
        verbose_name='Orijinal Dosya Adı'
    )
    uploaded_file = models.FileField(
        upload_to='imports/%Y/%m/%d/',
        verbose_name='Yüklenen Dosya'
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        verbose_name='Yükleyen'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        verbose_name='Durum'
    )
    item_count = models.IntegerField(default=0, verbose_name='Madde Sayısı')
    error_count = models.IntegerField(default=0, verbose_name='Hata Sayısı')

    class Meta:
        verbose_name = 'İçe Aktarma Grubu'
        verbose_name_plural = 'İçe Aktarma Grupları'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.original_filename} ({self.created_at|date:'d.m.Y'})"


class DraftItem(models.Model):
    """
    Henüz sisteme aktarılmamış, inceleme bekleyen taslak madde.
    """
    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Onay Bekliyor'
        APPROVED = 'APPROVED', 'Onaylandı'
        REJECTED = 'REJECTED', 'Reddedildi'

    batch = models.ForeignKey(
        ImportBatch,
        on_delete=models.CASCADE,
        related_name='draft_items',
        verbose_name='Yükleme Grubu'
    )
    stem = models.TextField(verbose_name='Madde Kökü')
    choices_json = models.JSONField(verbose_name='Şıklar (JSON)')
    correct_answer = models.CharField(
        max_length=10, 
        null=True, 
        blank=True,
        verbose_name='Doğru Cevap'
    )
    manual_review = models.BooleanField(
        default=False, 
        verbose_name='Manuel İnceleme Gerekli'
    )
    review_note = models.TextField(
        null=True, 
        blank=True, 
        verbose_name='İnceleme Notu'
    )
    ai_suggestions = models.JSONField(
        null=True, 
        blank=True, 
        verbose_name='AI Önerileri'
    )
    learning_outcomes = models.ManyToManyField(
        'LearningOutcome',
        blank=True,
        verbose_name='Öğrenme Çıktıları'
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        verbose_name='Durum'
    )
    
    # Gerçek Item oluşturulduğunda referans tutmak için (opsiyonel)
    # item = models.ForeignKey('Item', on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        verbose_name = 'Taslak Madde'
        verbose_name_plural = 'Taslak Maddeler'

    def __str__(self):
        return f"Taslak: {self.stem[:50]}..."
