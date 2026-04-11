from django.db import models

class AIPrompt(models.Model):
    """
    Uygulama genelinde kullanılan AI prompt şablonlarını yönetir.
    Kod tarafında sabit olan prompt metinlerinin veritabanından yönetilmesini sağlar.
    """
    slug = models.SlugField(
        max_length=100, 
        unique=True, 
        verbose_name="Kısa Kod (Slug)",
        help_text="Kod içerisinden bu prompt'u çağırmak için kullanılacak benzersiz isim (örn: ITEM_GENERATE)."
    )
    name = models.CharField(
        max_length=200, 
        verbose_name="Prompt Başlığı"
    )
    description = models.TextField(
        blank=True, 
        verbose_name="Açıklama/Kullanım Amacı"
    )
    system_instruction = models.TextField(
        blank=True, 
        verbose_name="Sistem Talimatı (System Instruction)",
        help_text="Modelin kişiliğini ve genel davranış kurallarını belirler (örn: 'Sen bir fizik öğretmenisin')."
    )
    template = models.TextField(
        verbose_name="Prompt Şablonu",
        help_text="Değişkenleri süslü parantez içinde belirtin. Örn: 'Aşağıdaki soruyu incele: {stem}'"
    )
    is_active = models.BooleanField(
        default=True, 
        verbose_name="Aktif"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "AI Prompt Şablonu"
        verbose_name_plural = "AI Prompt Şablonları"
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.slug})"

    def format_prompt(self, **kwargs):
        """Şablondaki değişkenleri verilen verilerle doldurur."""
        try:
            return self.template.format(**kwargs)
        except KeyError as e:
            return f"Eksik değişken hatası: {str(e)}"
        except Exception as e:
            return f"Format hatası: {str(e)}"
