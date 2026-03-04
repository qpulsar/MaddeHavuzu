from django.db import models
from .item import Item
from .pool import LearningOutcome

class OutcomeSuggestion(models.Model):
    """
    Bir madde için AI tarafından önerilen öğrenme çıktısı.
    """
    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Beklemede'
        ACCEPTED = 'ACCEPTED', 'Kabul Edildi'
        REJECTED = 'REJECTED', 'Reddedildi'

    item = models.ForeignKey(
        Item,
        on_delete=models.CASCADE,
        related_name='outcome_suggestions',
        verbose_name='Madde'
    )
    learning_outcome = models.ForeignKey(
        LearningOutcome,
        on_delete=models.CASCADE,
        related_name='suggestions',
        verbose_name='Önerilen Çıktı'
    )
    score = models.FloatField(default=0.0, verbose_name='Güven Skoru (0-1)')
    reasoning = models.TextField(null=True, blank=True, verbose_name='AI Gerekçesi')
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        verbose_name='Durum'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Çıktı Önerisi'
        verbose_name_plural = 'Çıktı Önerileri'
        ordering = ['-score']

    def __str__(self):
        return f"Öneri: {self.learning_outcome.code} (Skor: {self.score})"
