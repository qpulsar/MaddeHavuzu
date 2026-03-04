from django.db import models
from django.contrib.auth.models import User
from .pool import ItemPool, LearningOutcome


class Item(models.Model):
    """
    Merkezi Madde tablosu. Temel soru verisini tutar.
    """
    class ItemType(models.TextChoices):
        MULTIPLE_CHOICE = 'MCQ', 'Çoktan Seçmeli'
        TRUE_FALSE = 'TF', 'Doğru-Yanlış'
        MATCHING = 'MATCHING', 'Eşleştirme'
        OPEN_ENDED = 'OPEN', 'Açık Uçlu'

    class Difficulty(models.TextChoices):
        EASY = 'EASY', 'Kolay'
        MEDIUM = 'MEDIUM', 'Orta'
        HARD = 'HARD', 'Zor'

    class Status(models.TextChoices):
        DRAFT = 'DRAFT', 'Taslak'
        ACTIVE = 'ACTIVE', 'Aktif'
        RETIRED = 'RETIRED', 'Emekli/Kullanımdan Kaldırılmış'

    stem = models.TextField(
        verbose_name='Madde Kökü (Soru)'
    )
    item_type = models.CharField(
        max_length=20,
        choices=ItemType.choices,
        default=ItemType.MULTIPLE_CHOICE,
        verbose_name='Soru Tipi'
    )
    difficulty_intended = models.CharField(
        max_length=20,
        choices=Difficulty.choices,
        default=Difficulty.MEDIUM,
        verbose_name='Hedeflenen Zorluk'
    )
    author = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='authored_items',
        verbose_name='Yazar'
    )
    version = models.IntegerField(
        default=1,
        verbose_name='Sürüm'
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
        verbose_name='Durum'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Madde'
        verbose_name_plural = 'Maddeler'
        ordering = ['-created_at']

    def __str__(self):
        return f"Madde #{self.id} - Sürüm {self.version}"


class ItemChoice(models.Model):
    """
    Çoktan seçmeli sorular için seçenekler (şıklar).
    """
    item = models.ForeignKey(
        Item,
        on_delete=models.CASCADE,
        related_name='choices',
        verbose_name='Madde'
    )
    label = models.CharField(
        max_length=5,
        verbose_name='Seçenek Etiketi',
        help_text='Örn: A, B, C, D, E'
    )
    text = models.TextField(
        verbose_name='Seçenek Metni'
    )
    is_correct = models.BooleanField(
        default=False,
        verbose_name='Doğru Cevap mı?'
    )
    order = models.IntegerField(
        default=0,
        verbose_name='Sıralama'
    )

    class Meta:
        verbose_name = 'Madde Seçeneği'
        verbose_name_plural = 'Madde Seçenekleri'
        ordering = ['item', 'order', 'label']
        unique_together = ['item', 'label']

    def __str__(self):
        return f"{self.item.id} - {self.label}"


class ItemInstance(models.Model):
    """
    Madde-Havuz bağlantı tablosu.
    Aynı madde birden fazla havuza eklenebileceği için bu tablo havuz bazlı bilgileri tutar.
    """
    pool = models.ForeignKey(
        ItemPool,
        on_delete=models.CASCADE,
        related_name='item_instances',
        verbose_name='Havuz'
    )
    item = models.ForeignKey(
        Item,
        on_delete=models.CASCADE,
        related_name='instances',
        verbose_name='Madde'
    )
    learning_outcomes = models.ManyToManyField(
        LearningOutcome,
        blank=True,
        related_name='assigned_items',
        verbose_name='Öğrenme Çıktıları (Kazanımlar)'
    )
    is_fork = models.BooleanField(
        default=False,
        verbose_name='Kopyalandı (Forked)'
    )
    forked_from = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='forks',
        verbose_name='Kaynak Madde Bağlantısı'
    )
    added_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Eklenme Tarihi'
    )
    added_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='added_item_instances',
        verbose_name='Ekleyen Kullanıcı'
    )

    class Meta:
        verbose_name = 'Havuzdaki Madde'
        verbose_name_plural = 'Havuzdaki Maddeler'
        ordering = ['pool', '-added_at']
        unique_together = ['pool', 'item']  # Aynı havuzda aynı madde 1 kez olabilir

    def __str__(self):
        return f"Havuz: {self.pool.name} - Madde: {self.item.id}"
