"""
Kopya Analizi modelleri.

Kaynak modül Excel yüklemelerini data/ klasöründe, analiz sonuçlarını süreç
belleğinde tutuyordu (sunucu yeniden başlayınca kayboluyordu). Burada ikisi de
veritabanındadır.
"""
from django.conf import settings
from django.db import models


class KopyaUpload(models.Model):
    """Excel dosyasıyla yüklenmiş sınav verisi (kaynak: data/cheating_uploads/xl_<uid>)."""

    upload_id = models.CharField(max_length=40, unique=True, db_index=True)  # "xl_<uid16>"
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                              related_name='kopya_uploads', verbose_name='Yükleyen')
    file = models.FileField('Excel dosyası', upload_to='kopya/uploads/')
    original_filename = models.CharField('Dosya adı', max_length=255)
    meta = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Kopya Excel Yüklemesi'
        verbose_name_plural = 'Kopya Excel Yüklemeleri'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.original_filename} ({self.upload_id})"


class KopyaAnalysis(models.Model):
    """Hesaplanmış analyze_exam sonucu (pickle). Anahtar: kaynak + alpha + girdi özeti."""

    source_id = models.CharField(max_length=64, db_index=True)  # optik batch_id veya xl_<uid>
    alpha = models.FloatField()
    input_hash = models.CharField(max_length=32)
    result = models.BinaryField()
    computed_at = models.DateTimeField(auto_now_add=True)
    duration_seconds = models.FloatField(default=0)

    class Meta:
        verbose_name = 'Kopya Analiz Sonucu'
        verbose_name_plural = 'Kopya Analiz Sonuçları'
        ordering = ['-computed_at']
        constraints = [
            models.UniqueConstraint(fields=['source_id', 'alpha', 'input_hash'], name='kopya_analysis_unique_key'),
        ]

    def __str__(self):
        return f"{self.source_id} α={self.alpha}"
