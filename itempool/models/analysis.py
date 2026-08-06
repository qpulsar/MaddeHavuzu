from django.db import models
from .item import ItemInstance

class ItemAnalysisResult(models.Model):
    """
    Bir maddenin belirli bir sınav (TestForm) sonrasındaki analiz sonuçları.
    """
    item_instance = models.ForeignKey(
        ItemInstance,
        on_delete=models.CASCADE,
        related_name='analysis_results',
        verbose_name='Madde Kaydı'
    )
    test_form = models.ForeignKey(
        'TestForm',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='item_analysis_results',
        verbose_name='Sınav Formu'
    )
    upload_session = models.ForeignKey(
        'grading.UploadSession',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='item_analysis_results',
        verbose_name='Yükleme Oturumu'
    )
    
    difficulty_p = models.FloatField(default=0.0, verbose_name='Zorluk İndeksi (p)')
    discrimination_r = models.FloatField(default=0.0, verbose_name='Ayırt Edicilik (r)')
    distractor_efficiency = models.FloatField(default=0.0, verbose_name='Çeldirici Verimliliği')
    
    flagged = models.BooleanField(default=False, verbose_name='Sorunlu Madde mi?')
    risk_score = models.IntegerField(default=0, verbose_name='Risk Skoru (0-100)')
    
    analysis_data_json = models.JSONField(default=dict, verbose_name='Detaylı Analiz Verisi')
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Madde Analiz Sonucu'
        verbose_name_plural = 'Madde Analiz Sonuçları'
        ordering = ['-created_at']

    def calculate_risk(self):
        """
        Zorluk ve ayırt edicilik değerlerine göre risk skorunu hesaplar.
        0-30: Yeşil, 31-60: Sarı, 61-100: Kırmızı
        """
        risk = 0
        if self.discrimination_r < 0.2:
            risk += 50
        elif self.discrimination_r < 0.3:
            risk += 20
            
        if self.difficulty_p < 0.2 or self.difficulty_p > 0.9:
            risk += 30
        
        self.risk_score = min(risk, 100)
        self.flagged = self.risk_score > 60

        # Faz 3: Risk skoru Kırmızı (flagged) ise bağlı Item'ı Revizyon Gerektiriyor olarak işaretle
        try:
            if self.flagged and self.item_instance and self.item_instance.item:
                item = self.item_instance.item
                if item.status == 'ACTIVE':
                    item.status = 'NEEDS_REVISION'
                    item.save(update_fields=['status'])
        except Exception:
            pass

        return self.risk_score

    @property
    def risk_color(self):
        if self.risk_score <= 30: return "success"
        if self.risk_score <= 60: return "warning"
        return "danger"

    @property
    def p_comment(self):
        if self.difficulty_p > 0.85: return "Çok Kolay"
        if self.difficulty_p < 0.15: return "Çok Zor"
        return "Orta Güçlük"

    @property
    def r_comment(self):
        if self.discrimination_r < 0.19: return "Ayırt Edici Değil"
        if self.discrimination_r < 0.29: return "Zayıf Ayırt Edici"
        if self.discrimination_r < 0.39: return "İyi Ayırt Edici"
        return "Çok İyi Ayırt Edici"

    @property
    def student_sample_size(self):
        return self.analysis_data_json.get('student_sample_size') or (self.upload_session.student_count if self.upload_session else 0)

    @property
    def is_small_sample(self):
        size = self.student_sample_size
        return size > 0 and size < 30

    def __str__(self):
        return f"Analiz #{self.id} (Madde {self.item_instance.item_id})"
