from django.db import models
from django.contrib.auth.models import User
from grading.models.file_format import FileFormatConfig
# itempool.TestForm FK için lazy import kullanılıyor (circular import önlemi)
# bkz. test_form alanı


class ProcessingStatus(models.TextChoices):
    """Upload processing status choices."""
    QUEUED = 'QUEUED', 'Kuyrukta'
    PROCESSING = 'PROCESSING', 'İşleniyor'
    PROCESSED = 'PROCESSED', 'İşlendi'
    FAILED = 'FAILED', 'Başarısız'


class UploadSession(models.Model):
    """
    Represents a file upload and processing session.
    Each upload creates a new session with its own results.
    """
    owner = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='upload_sessions',
        verbose_name='Yükleyen'
    )
    original_filename = models.CharField(
        max_length=255,
        verbose_name='Dosya Adı'
    )
    uploaded_file = models.FileField(
        upload_to='uploads/%Y/%m/',
        verbose_name='Dosya'
    )
    file_format = models.ForeignKey(
        FileFormatConfig,
        on_delete=models.SET_NULL,
        null=True,
        verbose_name='Dosya Formatı'
    )
    
    # Processing metadata
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Yükleme Tarihi'
    )
    processed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='İşlenme Tarihi'
    )
    processing_status = models.CharField(
        max_length=20,
        choices=ProcessingStatus.choices,
        default=ProcessingStatus.QUEUED,
        verbose_name='Durum'
    )
    
    # Results summary
    question_count = models.IntegerField(
        null=True,
        blank=True,
        verbose_name='Soru Sayısı'
    )
    student_count = models.IntegerField(
        null=True,
        blank=True,
        verbose_name='Öğrenci Sayısı'
    )
    error_count = models.IntegerField(
        default=0,
        verbose_name='Hata Sayısı'
    )
    has_multiple_keys = models.BooleanField(
        default=False,
        verbose_name='Çoklu Anahtar'
    )
    
    # Error information
    error_summary = models.TextField(
        blank=True,
        verbose_name='Hata Özeti'
    )
    
    answer_key = models.TextField(
        blank=True,
        verbose_name='Cevap Anahtarı'
    )

    # Faz 13: TestForm ile bağlantı (opsiyonel)
    test_form = models.ForeignKey(
        'itempool.TestForm',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='upload_sessions',
        verbose_name='İlişkili Test Formu',
        help_text='Bu yükleme hangi test formunun değerlendirmesi için?'
    )

    wrong_to_correct_ratio = models.IntegerField(
        null=True,
        blank=True,
        default=0,
        verbose_name='Yanlış Doğru Oranı',
        help_text='Kaç yanlış bir doğruyu götürür? (Örn: 4)'
    )
    
    points_per_question = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=1.0,
        verbose_name='Soru Puanı',
        help_text='Her bir netin kaç puan değerinde olduğu (Örn: 1.0 veya 2.5)'
    )
    
    class Meta:
        verbose_name = 'Yükleme Oturumu'
        verbose_name_plural = 'Yükleme Oturumları'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.original_filename} - {self.owner.username} ({self.created_at.strftime('%d.%m.%Y %H:%M')})"
    
    @property
    def is_processed(self):
        return self.processing_status == ProcessingStatus.PROCESSED
    
    @property
    def is_failed(self):
        return self.processing_status == ProcessingStatus.FAILED


class StudentResult(models.Model):
    """
    Individual student result from an upload session.
    Stores both raw data and calculated scores.
    """
    upload_session = models.ForeignKey(
        UploadSession,
        on_delete=models.CASCADE,
        related_name='results',
        verbose_name='Yükleme Oturumu'
    )
    
    # Student identification
    student_no = models.CharField(
        max_length=50,
        blank=True,
        verbose_name='Öğrenci No'
    )
    student_name = models.CharField(
        max_length=255,
        verbose_name='Ad Soyad'
    )
    booklet = models.CharField(
        max_length=10,
        blank=True,
        verbose_name='Kitapçık'
    )
    
    # Raw data
    answers_raw = models.TextField(
        verbose_name='Ham Cevaplar'
    )
    row_number_in_file = models.IntegerField(
        verbose_name='Satır No'
    )
    
    # Calculated results
    correct_count = models.IntegerField(
        default=0,
        verbose_name='Doğru'
    )
    wrong_count = models.IntegerField(
        default=0,
        verbose_name='Yanlış'
    )
    blank_count = models.IntegerField(
        default=0,
        verbose_name='Boş'
    )
    invalid_count = models.IntegerField(
        default=0,
        verbose_name='Geçersiz'
    )
    net = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name='Net'
    )
    score = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name='Puan'
    )
    
    # Detailed results (question by question: D/Y/B/G)
    detailed_results = models.TextField(
        blank=True,
        verbose_name='Detaylı Sonuçlar',
        help_text='Her soru için D(oğru)/Y(anlış)/B(oş)/G(eçersiz)'
    )
    
    class Meta:
        verbose_name = 'Öğrenci Sonucu'
        verbose_name_plural = 'Öğrenci Sonuçları'
        ordering = ['row_number_in_file']
    
    def __str__(self):
        return f"{self.student_name} - D:{self.correct_count} Y:{self.wrong_count} B:{self.blank_count}"


class ParsingError(models.Model):
    """
    Records errors encountered during file parsing.
    Allows users to see which lines were skipped and why.
    """
    upload_session = models.ForeignKey(
        UploadSession,
        on_delete=models.CASCADE,
        related_name='parsing_errors',
        verbose_name='Yükleme Oturumu'
    )
    row_number = models.IntegerField(
        verbose_name='Satır No'
    )
    raw_line = models.TextField(
        verbose_name='Ham Satır'
    )
    message = models.CharField(
        max_length=500,
        verbose_name='Hata Mesajı'
    )
    created_at = models.DateTimeField(
        auto_now_add=True
    )
    
    class Meta:
        verbose_name = 'Ayrıştırma Hatası'
        verbose_name_plural = 'Ayrıştırma Hataları'
        ordering = ['row_number']
    
    def __str__(self):
        return f"Satır {self.row_number}: {self.message[:50]}"
