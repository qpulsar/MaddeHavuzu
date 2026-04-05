from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator


class ExamTemplate(models.Model):
    """
    Sınav kağıdının sayfa düzeni şablonu.
    Sütun sayısı, font, boşluklar, üst/alt bilgi gibi baskı özelliklerini tutar.
    """

    class FontChoice(models.TextChoices):
        TIMES = 'Times New Roman, serif', 'Times New Roman'
        ARIAL = 'Arial, sans-serif', 'Arial'
        HELVETICA = 'Helvetica, sans-serif', 'Helvetica'
        GEORGIA = 'Georgia, serif', 'Georgia'
        CALIBRI = 'Calibri, sans-serif', 'Calibri'

    class PageSize(models.TextChoices):
        A4 = 'A4', 'A4 (210×297 mm)'
        A5 = 'A5', 'A5 (148×210 mm)'
        LETTER = 'LETTER', 'Letter (216×279 mm)'

    class ChoiceLayout(models.TextChoices):
        VERTICAL = 'vertical', 'Dikey (alt alta)'
        HORIZONTAL = 'horizontal', 'Yatay (yan yana)'
        AUTO = 'auto', 'Otomatik (Uzunluğa göre)'

    name = models.CharField(
        max_length=200,
        verbose_name='Şablon Adı'
    )
    is_default = models.BooleanField(
        default=False,
        verbose_name='Varsayılan Şablon',
        help_text='Seçilirse bu şablon varsayılan olarak kullanılır'
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='exam_templates',
        verbose_name='Oluşturan'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Sayfa yapısı
    page_size = models.CharField(
        max_length=20,
        choices=PageSize.choices,
        default=PageSize.A4,
        verbose_name='Kağıt Boyutu'
    )
    column_count = models.IntegerField(
        default=1,
        validators=[MinValueValidator(1), MaxValueValidator(3)],
        verbose_name='Sütun Sayısı',
        help_text='1, 2 veya 3 sütun'
    )
    column_divider = models.BooleanField(
        default=True,
        verbose_name='Sütunlar Arası Çizgi'
    )
    margin_top = models.IntegerField(
        default=25,
        verbose_name='Üst Kenar Boşluğu (mm)'
    )
    margin_bottom = models.IntegerField(
        default=25,
        verbose_name='Alt Kenar Boşluğu (mm)'
    )
    margin_left = models.IntegerField(
        default=20,
        verbose_name='Sol Kenar Boşluğu (mm)'
    )
    margin_right = models.IntegerField(
        default=20,
        verbose_name='Sağ Kenar Boşluğu (mm)'
    )

    # Tipografi
    font_family = models.CharField(
        max_length=100,
        choices=FontChoice.choices,
        default=FontChoice.TIMES,
        verbose_name='Font'
    )
    font_size = models.IntegerField(
        default=11,
        validators=[MinValueValidator(8), MaxValueValidator(16)],
        verbose_name='Font Boyutu (pt)'
    )
    question_spacing = models.IntegerField(
        default=12,
        validators=[MinValueValidator(4), MaxValueValidator(30)],
        verbose_name='Sorular Arası Boşluk (pt)'
    )
    choice_layout = models.CharField(
        max_length=20,
        choices=ChoiceLayout.choices,
        default=ChoiceLayout.VERTICAL,
        verbose_name='Seçenek Dizilimi'
    )
    choice_spacing = models.IntegerField(
        default=2,
        validators=[MinValueValidator(0), MaxValueValidator(20)],
        verbose_name='Seçenek Aralığı (pt)',
        help_text='Şıklar arasındaki dikey boşluk'
    )

    # Üst bilgi
    header_left = models.CharField(
        max_length=300,
        blank=True,
        verbose_name='Üst Bilgi (Sol)',
        help_text='Örn: Kurum adı. {course}, {semester}, {date} değişkenlerini kullanabilirsiniz.'
    )
    header_center = models.CharField(
        max_length=300,
        blank=True,
        verbose_name='Üst Bilgi (Orta)',
        help_text='Örn: {form_name}'
    )
    header_right = models.CharField(
        max_length=300,
        blank=True,
        verbose_name='Üst Bilgi (Sağ)',
        help_text='Örn: Tarih: {date}'
    )
    show_header_line = models.BooleanField(
        default=True,
        verbose_name='Üst Bilgi Altına Çizgi'
    )

    # Alt bilgi
    footer_left = models.CharField(
        max_length=300,
        blank=True,
        verbose_name='Alt Bilgi (Sol)'
    )
    footer_center = models.CharField(
        max_length=300,
        blank=True,
        verbose_name='Alt Bilgi (Orta)',
        help_text='Örn: Sayfa {page}/{total_pages}'
    )
    footer_right = models.CharField(
        max_length=300,
        blank=True,
        verbose_name='Alt Bilgi (Sağ)'
    )
    show_footer_line = models.BooleanField(
        default=True,
        verbose_name='Alt Bilgi Üstüne Çizgi'
    )

    # Öğrenci bilgi alanı
    show_student_info_box = models.BooleanField(
        default=True,
        verbose_name='Öğrenci Bilgi Kutusu',
        help_text='Ad Soyad, No, Tarih için boş alan'
    )
    show_question_points = models.BooleanField(
        default=True,
        verbose_name="Soru Puanlarını Göster",
        help_text="Her sorunun yanında puanını göster"
    )

    header_html = models.TextField(
        null=True,
        blank=True,
        verbose_name='Özel Başlık (HTML)',
        help_text='Zengin metin editörü veya Word dosyasından aktarılan başlık içeriği'
    )
    footer_html = models.TextField(
        null=True,
        blank=True,
        verbose_name='Özel Alt Bilgi (HTML)',
        help_text='Zengin metin editörü ile oluşturulan alt bilgi içeriği'
    )

    class Meta:
        verbose_name = 'Sınav Kağıdı Şablonu'
        verbose_name_plural = 'Sınav Kağıdı Şablonları'
        ordering = ['-is_default', 'name']

    def __str__(self):
        return self.name

    @classmethod
    def get_default(cls):
        return cls.objects.filter(is_default=True).first() or cls.objects.first()
