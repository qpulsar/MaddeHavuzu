"""
Optik Okuma modelleri.

Kaynak modül (omr_analysis) verisini JSON dosyalarında tutuyordu. Burada her
varlık bir Django modelidir; iç içe alanlar `data` JSONField'ında, sorgu ve
yetki için gereken alanlar ayrıca sütun olarak tutulur. Servis katmanı
`optik.store` üzerinden dict alıp verir, böylece iş mantığı kaynakla aynı kalır.
"""
from django.conf import settings
from django.db import models


class OptikTest(models.Model):
    """Optik sınav tanımı (kitapçıklar, cevap anahtarları, madde puanları)."""

    test_id = models.CharField(max_length=32, unique=True, db_index=True)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='optik_tests', verbose_name='Oluşturan')
    course_code = models.CharField('Ders Kodu', max_length=50, blank=True)
    course_name = models.CharField('Ders Adı', max_length=255, blank=True)
    exam_type = models.CharField('Sınav Türü', max_length=100, blank=True)
    academic_year = models.CharField('Akademik Yıl', max_length=20, blank=True)
    semester = models.CharField('Dönem', max_length=20, blank=True)
    is_approved = models.BooleanField(default=False)
    deleted = models.BooleanField(default=False)
    data = models.JSONField('Test verisi', default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Optik Test'
        verbose_name_plural = 'Optik Testler'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.course_code} - {self.exam_type} ({self.test_id})"


class OptikBatch(models.Model):
    """Bir teste ait form yükleme grubu; puanlama sonucu `scores` alanındadır."""

    batch_id = models.CharField(max_length=32, unique=True, db_index=True)
    test = models.ForeignKey(OptikTest, on_delete=models.CASCADE, related_name='batches')
    status = models.CharField(max_length=32, default='CREATED')
    data = models.JSONField('Batch verisi', default=dict)
    scores = models.JSONField('Puanlama sonucu', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Optik Batch'
        verbose_name_plural = 'Optik Batch\'ler'
        ordering = ['-created_at']

    def __str__(self):
        return self.batch_id


class OptikRecord(models.Model):
    """Okunan tek bir optik form."""

    batch = models.ForeignKey(OptikBatch, on_delete=models.CASCADE, related_name='records')
    record_id = models.CharField(max_length=64, db_index=True)
    student_no = models.CharField(max_length=32, blank=True, db_index=True)
    booklet = models.CharField(max_length=8, blank=True)
    data = models.JSONField('Kayıt verisi', default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Optik Kayıt'
        verbose_name_plural = 'Optik Kayıtlar'
        ordering = ['created_at', 'id']
        constraints = [
            models.UniqueConstraint(fields=['batch', 'record_id'], name='optik_record_unique_in_batch'),
        ]

    def __str__(self):
        return f"{self.record_id} ({self.student_no})"


class OptikSnapshot(models.Model):
    """Onay anındaki kayıtların değişmez kopyası."""

    batch = models.ForeignKey(OptikBatch, on_delete=models.CASCADE, related_name='snapshots')
    version = models.CharField(max_length=16)
    metadata = models.JSONField(default=dict)
    records = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Optik Snapshot'
        verbose_name_plural = 'Optik Snapshot\'lar'
        ordering = ['batch', 'created_at']
        constraints = [
            models.UniqueConstraint(fields=['batch', 'version'], name='optik_snapshot_unique_version'),
        ]

    def __str__(self):
        return f"{self.batch.batch_id} {self.version}"
