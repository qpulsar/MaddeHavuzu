from django.db import models
from django.contrib.auth.models import User


class ItemPool(models.Model):
    """
    Madde Havuzu tablosu. Ders/Sınav havuzlarını temsil eder.
    """
    class Status(models.TextChoices):
        ACTIVE = 'ACTIVE', 'Aktif'
        ARCHIVED = 'ARCHIVED', 'Arşivlendi'
    
    name = models.CharField(
        max_length=200,
        verbose_name='Havuz Adı'
    )
    course = models.CharField(
        max_length=200,
        verbose_name='Ders Adı'
    )
    semester = models.CharField(
        max_length=20,
        verbose_name='Dönem',
        help_text='Örn: 2024-Güz'
    )
    level = models.CharField(
        max_length=20,
        verbose_name='Eğitim Düzeyi',
        help_text='Örn: Lisans 1, Yüksek Lisans'
    )
    tags = models.JSONField(
        default=list,
        blank=True,
        verbose_name='Etiketler'
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
        verbose_name='Durum'
    )
    owner = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='owned_pools',
        verbose_name='Havuz Sahibi'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Madde Havuzu'
        verbose_name_plural = 'Madde Havuzları'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} ({self.semester})"


class LearningOutcome(models.Model):
    """
    Öğrenme Çıktısı tablosu. Havuzlara özel olarak tanımlanır.
    """
    class BloomLevel(models.TextChoices):
        KNOWLEDGE = 'KNOWLEDGE', 'Bilgi'
        COMPREHENSION = 'COMPREHENSION', 'Kavrama'
        APPLICATION = 'APPLICATION', 'Uygulama'
        ANALYSIS = 'ANALYSIS', 'Analiz'
        SYNTHESIS = 'SYNTHESIS', 'Sentez'
        EVALUATION = 'EVALUATION', 'Değerlendirme'

    pool = models.ForeignKey(
        ItemPool,
        on_delete=models.CASCADE,
        related_name='outcomes',
        verbose_name='Havuz'
    )
    code = models.CharField(
        max_length=20,
        verbose_name='Çıktı Kodu',
        help_text='Örn: ÖÇ1, KAZ1'
    )
    description = models.TextField(
        verbose_name='Açıklama'
    )
    level = models.CharField(
        max_length=30,
        choices=BloomLevel.choices,
        default=BloomLevel.KNOWLEDGE,
        verbose_name='Bilişsel Düzey (Bloom)'
    )
    weight = models.FloatField(
        null=True,
        blank=True,
        verbose_name='Ağırlık (%)'
    )
    order = models.IntegerField(
        default=0,
        verbose_name='Sıralama'
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name='Aktif'
    )

    class Meta:
        verbose_name = 'Öğrenme Çıktısı'
        verbose_name_plural = 'Öğrenme Çıktıları'
        ordering = ['pool', 'order', 'code']
        unique_together = ['pool', 'code']

    def __str__(self):
        return f"{self.code} - {self.description[:50]}"


class PoolPermission(models.Model):
    """
    Havuz bazlı yetkilendirme tablosu.
    """
    class PermissionLevel(models.TextChoices):
        VIEWER = 'VIEWER', 'Görüntüleyebilir'
        EDITOR = 'EDITOR', 'Düzenleyebilir'
        MANAGER = 'MANAGER', 'Yönetebilir (Silme/Yetki Verme)'

    pool = models.ForeignKey(
        ItemPool,
        on_delete=models.CASCADE,
        related_name='permissions',
        verbose_name='Havuz'
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='pool_permissions',
        verbose_name='Kullanıcı'
    )
    level = models.CharField(
        max_length=20,
        choices=PermissionLevel.choices,
        default=PermissionLevel.VIEWER,
        verbose_name='Yetki Seviyesi'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Havuz Yetkisi'
        verbose_name_plural = 'Havuz Yetkileri'
        unique_together = ['pool', 'user']

    def __str__(self):
        return f"{self.user.username} - {self.pool.name} ({self.get_level_display()})"
