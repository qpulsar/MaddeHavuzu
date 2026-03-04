from django.db import models
from django.contrib.auth.models import User
from .item import Item

class ItemAuditLog(models.Model):
    """
    Madde üzerinde yapılan değişikliklerin kaydı.
    """
    item = models.ForeignKey(
        Item,
        on_delete=models.CASCADE,
        related_name='audit_logs',
        verbose_name='Madde'
    )
    action = models.CharField(
        max_length=50,
        verbose_name='Eylem' # CREATE, UPDATE, DELETE, STATUS_CHANGE
    )
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        verbose_name='Kullanıcı'
    )
    details_json = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='Değişiklik Detayları'
    )
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Madde İşlem Kaydı'
        verbose_name_plural = 'Madde İşlem Kayıtları'
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.item_id} - {self.action} - {self.timestamp}"
