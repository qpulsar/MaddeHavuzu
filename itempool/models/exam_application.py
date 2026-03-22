from django.db import models
from django.contrib.auth.models import User
from .pool import ItemPool
from .test_form import TestForm


class Course(models.Model):
    """
    Ders modeli. Bir dönemde verilen dersi temsil eder.
    Derse ait sınav formları ve belirtke tabloları bu modele bağlıdır.
    """
    name = models.CharField(
        max_length=200,
        verbose_name='Ders Adı',
        help_text='Örn: Eğitim Psikolojisi'
    )
    code = models.CharField(
        max_length=50,
        blank=True,
        verbose_name='Ders Kodu',
        help_text='Örn: EPD 201'
    )
    semester = models.CharField(
        max_length=100,
        verbose_name='Dönem',
        help_text='Örn: 2026-Güz'
    )
    description = models.TextField(
        blank=True,
        verbose_name='Açıklama'
    )
    pools = models.ManyToManyField(
        ItemPool,
        blank=True,
        related_name='courses',
        verbose_name='Bağlı Madde Havuzları',
        help_text='Bu derste kullanılacak madde havuzları'
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_courses',
        verbose_name='Oluşturan'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Ders'
        verbose_name_plural = 'Dersler'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} ({self.semester})"

    def get_applied_item_instance_ids(self):
        """Bu derse ait sınavlarda daha önce kullanılmış tüm madde instance ID'lerini döndürür."""
        return set(
            FormItem.objects.filter(
                form__applications__course=self
            ).values_list('item_instance_id', flat=True)
        )


class CourseSpecTable(models.Model):
    """
    Derse ait belirtke tablosu. Sınav oluştururken konu ve Bloom düzeyi
    dağılımını tanımlar. Otomatik soru seçiminde referans alınır.
    """
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name='spec_tables',
        verbose_name='Ders'
    )
    name = models.CharField(
        max_length=255,
        verbose_name='Tablo Adı',
        help_text='Örn: Vize Belirtke Tablosu'
    )
    # rows_json yapısı:
    # [
    #   {
    #     "topic": "Hafıza ve Öğrenme",
    #     "outcomes": [{"outcome_id": 1, "question_count": 5, "bloom_level": "APPLICATION"}],
    #     "total_questions": 5
    #   },
    #   ...
    # ]
    rows_json = models.JSONField(
        default=list,
        verbose_name='Tablo Verisi'
    )
    total_questions = models.PositiveIntegerField(
        default=0,
        verbose_name='Toplam Soru Sayısı'
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        verbose_name='Oluşturan'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Belirtke Tablosu'
        verbose_name_plural = 'Belirtke Tabloları'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} — {self.course}"


class ExamApplication(models.Model):
    """
    Bir sınav formunun belirli bir derse uygulandığını kaydeder.
    Soru tekrar etmeme için referans noktası.
    """
    test_form = models.ForeignKey(
        TestForm,
        on_delete=models.CASCADE,
        related_name='applications',
        verbose_name='Sınav Formu'
    )
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name='exam_applications',
        verbose_name='Ders'
    )
    applied_at = models.DateField(
        verbose_name='Uygulama Tarihi'
    )
    notes = models.TextField(
        null=True,
        blank=True,
        verbose_name='Notlar'
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_applications',
        verbose_name='Kaydeden'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Sınav Uygulaması'
        verbose_name_plural = 'Sınav Uygulamaları'
        ordering = ['-applied_at']
        unique_together = ['test_form', 'course']

    def __str__(self):
        return f"{self.test_form.name} → {self.course} ({self.applied_at})"


# Circular import'u önlemek için burada import
from .test_form import FormItem
