import os
import logging
from django.conf import settings
from dotenv import load_dotenv
from google import genai
from itempool.models import AIPrompt

# Proje kökündeki .env dosyasını yükle
load_dotenv()

logger = logging.getLogger(__name__)

class LLMClient:
    """
    Soyut LLM Client sınıfı. Farklı sağlayıcılar (OpenAI, Gemini vb.) için genişletilebilir.
    """
    def suggest_improvements(self, stem, choices):
        raise NotImplementedError

    def suggest_outcomes(self, stem, outcomes_list):
        raise NotImplementedError

    def generate_item(self, outcome_text, bloom_level, difficulty, item_type='MCQ'):
        raise NotImplementedError

    def suggest_distractors(self, stem, correct_answer):
        raise NotImplementedError

    def generate_variation(self, item_stem, choices):
        raise NotImplementedError

    def get_embedding(self, text):
        raise NotImplementedError


class GeminiClient(LLMClient):
    """
    Google Gemini API kullanarak öneri üreten istemci.
    Prompt'ları veritabanındaki AIPrompt modelinden dinamik olarak çeker.
    """
    def __init__(self):
        self.api_key = os.getenv('GEMINI_API_KEY')
        self.model_name = os.getenv('GEMINI_MODEL', 'gemini-1.5-flash')
        
        if not self.api_key:
            self.client = None
        else:
            self.client = genai.Client(api_key=self.api_key)

    def _get_prompt_config(self, slug, default_template, default_system=""):
        """Veritabanından prompt şablonunu ve sistem talimatını getirir."""
        try:
            prompt_obj = AIPrompt.objects.get(slug=slug, is_active=True)
            return prompt_obj.template, prompt_obj.system_instruction
        except AIPrompt.DoesNotExist:
            logger.warning(f"AIPrompt with slug {slug} not found or inactive. Using default.")
            return default_template, default_system
        except Exception as e:
            logger.error(f"Error fetching AIPrompt {slug}: {str(e)}")
            return default_template, default_system

    def _generate(self, prompt, system_instruction=""):
        if not self.client:
            return "API Key bulunamadı veya istemci yapılandırılamadı."
        
        try:
            # Gemini 2.0+ client structure allows config with system_instruction
            config = {}
            if system_instruction:
                config['system_instruction'] = system_instruction
            
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=config
            )
            return response.text
        except Exception as e:
            logger.error(f"Gemini API Error: {str(e)}")
            return f"Hata: {str(e)}"

    def suggest_improvements(self, stem, choices):
        default_tpl = """Aşağıdaki sınav sorusunu dil bilgisi, netlik ve bilimsel doğruluk açısından incele. 
Gerekirse madde kökünü (soruyu) ve şıkları iyileştir.

Soru: {stem}
Şıklar: {choices}

Lütfen sadece iyileştirilmiş versiyonu JSON formatında dön:
{{"improved_stem": "...", "improved_choices": [...]}}"""
        
        template, system = self._get_prompt_config('ITEM_IMPROVE', default_tpl)
        prompt = template.format(stem=stem, choices=choices)
        return self._generate(prompt, system)

    def suggest_outcomes(self, stem, outcomes_list):
        outcomes_text = "\n".join([f"- ID: {o.id}, Kod: {o.code}, Açıklama: {o.description}" for o in outcomes_list])
        default_tpl = """Aşağıdaki soruya en uygun öğrenme çıktısını seç.

Soru: {stem}

Öğrenme Çıktıları Listesi:
{outcomes_text}

Lütfen en uygun çıktının ID'sini, güven skorunu (0-1 arası) ve kısa gerekçesini JSON olarak dön:
{{"outcome_id": ..., "score": ..., "reason": "..."}}"""
        
        template, system = self._get_prompt_config('SUGGEST_OUTCOMES', default_tpl)
        prompt = template.format(stem=stem, outcomes_text=outcomes_text)
        return self._generate(prompt, system)

    def generate_item(self, outcome_text, bloom_level, difficulty, count=1, item_type='MCQ'):
        bloom_guidance = {
            "Bilgi": "Hatırlama düzeyinde, doğrudan tanım veya olgu sorusu.",
            "Kavrama": "Anlama düzeyinde, yorumlama ve açıklama gerektiren sorular.",
            "Uygulama": "Öğrenilen bilgiyi yeni bir durumda kullanma, problem çözme senaryoları.",
            "Analiz": "Parçalar arası ilişkileri belirleme, veriyi analiz etme.",
            "Sentez": "Yeni ve özgün bir ürün/çözüm kurgulama.",
            "Değerlendirme": "Yargıya varma, eleştirel değerlendirme yapma."
        }
        guidance = bloom_guidance.get(bloom_level, "Genel eğitim standartlarına uygun.")
        
        count_str = f"{count} adet " if count > 1 else ""
        format_str = """
        [
            {
                "stem": "Soru kökü buraya",
                "choices": [
                    {"label": "A", "text": "Seçenek A"},
                    {"label": "B", "text": "Seçenek B"},
                    {"label": "C", "text": "Seçenek C"},
                    {"label": "D", "text": "Seçenek D"}
                ],
                "correct_answer": "A"
            },
            ...
        ]
        """ if count > 1 else """
        {
            "stem": "Soru kökü buraya",
            "choices": [
                {"label": "A", "text": "Seçenek A"},
                {"label": "B", "text": "Seçenek B"},
                {"label": "C", "text": "Seçenek C"},
                {"label": "D", "text": "Seçenek D"}
            ],
            "correct_answer": "A"
        }
        """
        
        default_tpl = """Aşağıdaki öğrenme çıktısına (kazanıma) ve zorluk seviyesine uygun, {count_str}profesyonel sınav sorusu üret.

Öğrenme Çıktısı: {outcome_text}
Bloom Düzeyi: {bloom_level} ({guidance})
Zorluk Seviyesi: {difficulty}
Soru Tipi: {item_type}

Kalite Kuralları:
1. Türkçe imla kurallarına tam uyum.
2. Bilimsel doğruluk ve netlik.
3. Çeldiriciler mantıklı ve birbirine yakın uzunlukta olmalı.
4. "Hepsi" veya "Hiçbiri" gibi kaçamak şıklardan kaçın.
5. Madde kökünde olumsuz ifade varsa ("değildir", "olamaz" vb.) BÜYÜK harfle yaz.

Lütfen cevabı SADECE aşağıdaki JSON formatında dön:
{format_str}"""

        template, system = self._get_prompt_config('ITEM_GENERATE', default_tpl)
        prompt = template.format(
            outcome_text=outcome_text, 
            bloom_level=bloom_level, 
            guidance=guidance, 
            difficulty=difficulty, 
            item_type=item_type,
            count_str=count_str,
            format_str=format_str
        )
        return self._generate(prompt, system)

    def suggest_distractors(self, stem, correct_answer):
        default_tpl = """Aşağıdaki soru kökü ve doğru cevap için 3 adet mantıklı çeldirici (yanlış şık) üret.

Soru: {stem}
Doğru Cevap: {correct_answer}

Lütfen SADECE şu formatta bir JSON listesi dön:
["Çeldirici 1", "Çeldirici 2", "Çeldirici 3"]"""
        
        template, system = self._get_prompt_config('SUGGEST_DISTRACTORS', default_tpl)
        prompt = template.format(stem=stem, correct_answer=correct_answer)
        return self._generate(prompt, system)

    def generate_variation(self, item_stem, choices):
        default_tpl = """Aşağıdaki sınav sorusunun anlamsal olarak benzer ancak farklı bir versiyonunu üret (sayıları veya örnekleri değiştirerek).

Orijinal Soru: {stem}
Orijinal Şıklar: {choices}

Lütfen cevabı SADECE aşağıdaki JSON formatında dön:
{{
    "stem": "Yeni soru kökü",
    "choices": [
        {{"label": "A", "text": "Yeni Seçenek A"}},
        ...
    ],
    "correct_answer": "..."
}}"""
        
        template, system = self._get_prompt_config('GENERATE_VARIATION', default_tpl)
        # Note: input names in generate_variation were slightly different, aligning them to template
        prompt = template.format(stem=item_stem, choices=choices)
        return self._generate(prompt, system)

    def get_embedding(self, text):
        if not self.client:
            return None
        try:
            response = self.client.models.embed_content(
                model='text-embedding-004',
                contents=text
            )
            return response.embeddings[0].values
        except Exception as e:
            logger.error(f"Embedding Error: {str(e)}")
            return None


def get_llm_client():
    # Şimdilik varsayılan olarak Gemini dönüyoruz.
    return GeminiClient()
