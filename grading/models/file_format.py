from django.db import models


class FileFormatConfig(models.Model):
    """
    Admin-defined file format configuration.
    Allows admin to specify how TXT files from optical readers should be parsed.
    """
    
    class FormatType(models.TextChoices):
        FIXED_WIDTH = 'FIXED_WIDTH', 'Sabit Genişlik'
        DELIMITED = 'DELIMITED', 'Ayraçlı'
    
    name = models.CharField(
        max_length=100,
        verbose_name='Format Adı',
        help_text='Örn: "Optik Okuyucu v1", "Scantron 2000"'
    )
    description = models.TextField(
        blank=True,
        verbose_name='Açıklama'
    )
    
    # Format type
    format_type = models.CharField(
        max_length=20,
        choices=FormatType.choices,
        default=FormatType.FIXED_WIDTH,
        verbose_name='Format Tipi'
    )
    
    # Delimiter for DELIMITED format
    delimiter = models.CharField(
        max_length=10,
        blank=True,
        default='',
        verbose_name='Ayraç',
        help_text='Ayraçlı format için: ; , \\t (tab için \\t yazın)'
    )
    
    # Field positions for FIXED_WIDTH format
    student_no_start = models.IntegerField(
        default=0,
        verbose_name='Öğrenci No Başlangıç',
        help_text='0-indexed karakter pozisyonu'
    )
    student_no_end = models.IntegerField(
        default=12,
        verbose_name='Öğrenci No Bitiş',
        help_text='0-indexed karakter pozisyonu (dahil değil)'
    )
    student_name_start = models.IntegerField(
        default=15,
        verbose_name='Ad Soyad Başlangıç'
    )
    student_name_end = models.IntegerField(
        default=38,
        verbose_name='Ad Soyad Bitiş'
    )
    answers_start = models.IntegerField(
        default=38,
        verbose_name='Cevaplar Başlangıç'
    )
    answers_end = models.IntegerField(
        null=True,
        blank=True,
        verbose_name='Cevaplar Bitiş',
        help_text='Boş bırakılırsa satır sonuna kadar okunur'
    )
    
    # Booklet field (optional)
    has_booklet_field = models.BooleanField(
        default=False,
        verbose_name='Kitapçık Alanı Var mı?'
    )
    booklet_start = models.IntegerField(
        null=True,
        blank=True,
        verbose_name='Kitapçık Başlangıç'
    )
    booklet_end = models.IntegerField(
        null=True,
        blank=True,
        verbose_name='Kitapçık Bitiş'
    )
    
    # Key identification
    key_identifier = models.CharField(
        max_length=50,
        default='ANAHTAR',
        verbose_name='Anahtar Tanımlayıcı',
        help_text='Cevap anahtarını tanımlayan metin. Örn: ANAHTAR, CEVAP, 000000000000'
    )
    key_identifier_field = models.CharField(
        max_length=20,
        choices=[
            ('student_no', 'Öğrenci No'),
            ('student_name', 'Ad Soyad'),
        ],
        default='student_name',
        verbose_name='Anahtar Aranacak Alan'
    )
    
    # Valid answer options
    valid_options = models.CharField(
        max_length=20,
        default='ABCDE',
        verbose_name='Geçerli Şıklar',
        help_text='Örn: ABCDE veya ABCD'
    )
    
    # Blank markers
    blank_markers = models.CharField(
        max_length=20,
        default='-* .',
        verbose_name='Boş İşaretleri',
        help_text='Boş cevabı temsil eden karakterler. Örn: -* .'
    )
    
    # Status
    is_active = models.BooleanField(
        default=True,
        verbose_name='Aktif'
    )
    is_default = models.BooleanField(
        default=False,
        verbose_name='Varsayılan',
        help_text='Yeni yüklemelerde varsayılan olarak seçilsin'
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Oluşturulma Tarihi'
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='Güncelleme Tarihi'
    )
    
    class Meta:
        verbose_name = 'Dosya Formatı'
        verbose_name_plural = 'Dosya Formatları'
        ordering = ['-is_default', 'name']
    
    def __str__(self):
        return self.name
    
    def save(self, *args, **kwargs):
        # Ensure only one default format
        if self.is_default:
            FileFormatConfig.objects.filter(is_default=True).exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)
    
    def get_delimiter(self):
        """Get the actual delimiter character."""
        if self.delimiter == '\\t':
            return '\t'
        return self.delimiter
