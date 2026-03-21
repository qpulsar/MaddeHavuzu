from django.db import models
from django.contrib.auth.models import User
from .pool import ItemPool
from .test_form import TestForm


class StudentGroup(models.Model):
    """
    Bir dersi alan öğrenci grubu / sınıfı.
    Aynı sınava giren grup tanımlanarak soru tekrarı önlenir.
    """
    name = models.CharField(
        max_length=200,
        verbose_name='Grup Adı',
        help_text='Örn: Bilgisayar Müh. 2024-Güz Grup A'
    )
    course = models.CharField(
        max_length=200,
        verbose_name='Ders',
        help_text='Bu grubun aldığı ders'
    )
    semester = models.CharField(
        max_length=100,
        verbose_name='Dönem',
        help_text='Örn: 2024-Güz'
    )
    description = models.TextField(
        null=True,
        blank=True,
        verbose_name='Açıklama'
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_groups',
        verbose_name='Oluşturan'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Öğrenci Grubu'
        verbose_name_plural = 'Öğrenci Grupları'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} ({self.semester})"

    def get_applied_item_instance_ids(self):
        """Bu gruba daha önce uygulanmış tüm madde instance ID'lerini döndürür."""
        return set(
            FormItem.objects.filter(
                form__applications__group=self
            ).values_list('item_instance_id', flat=True)
        )


class ExamApplication(models.Model):
    """
    Bir test formunun belirli bir gruba uygulandığını kaydeder.
    Soru tekrar etmeme için referans noktası.
    """
    test_form = models.ForeignKey(
        TestForm,
        on_delete=models.CASCADE,
        related_name='applications',
        verbose_name='Test Formu'
    )
    group = models.ForeignKey(
        StudentGroup,
        on_delete=models.CASCADE,
        related_name='exam_applications',
        verbose_name='Öğrenci Grubu'
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
        unique_together = ['test_form', 'group']

    def __str__(self):
        return f"{self.test_form.name} → {self.group.name} ({self.applied_at})"


# Circular import'u önlemek için burada import
from .test_form import FormItem
