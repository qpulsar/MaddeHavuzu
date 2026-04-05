import os
from django.conf import settings
from dotenv import load_dotenv
from google import genai

# Proje kökündeki .env dosyasını yükle
load_dotenv()

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
    """
    def __init__(self):
        self.api_key = os.getenv('GEMINI_API_KEY')
        self.model_name = os.getenv('GEMINI_MODEL_NAME', 'gemini-1.5-flash')
        
        if not self.api_key:
            self.client = None
        else:
            self.client = genai.Client(api_key=self.api_key)

    def _generate(self, prompt):
        if not self.client:
            return "API Key bulunamadı veya istemci yapılandırılamadı."
        
        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt
            )
            return response.text
        except Exception as e:
            return f"Hata: {str(e)}"

    def suggest_improvements(self, stem, choices):
        prompt = f"""
        Aşağıdaki sınav sorusunu dil bilgisi, netlik ve bilimsel doğruluk açısından incele. 
        Gerekirse madde kökünü (soruyu) ve şıkları iyileştir.
        
        Soru: {stem}
        Şıklar: {choices}
        
        Lütfen sadece iyileştirilmiş versiyonu JSON formatında dön:
        {{"improved_stem": "...", "improved_choices": [...]}}
        """
        # Şimdilik basit tutuyoruz, Faz 3'te detaylandırılabilir.
        return self._generate(prompt)

    def suggest_outcomes(self, stem, outcomes_list):
        outcomes_text = "\n".join([f"- ID: {o.id}, Kod: {o.code}, Açıklama: {o.description}" for o in outcomes_list])
        prompt = f"""
        Aşağıdaki soruya en uygun öğrenme çıktısını seç.
        
        Soru: {stem}
        
        Öğrenme Çıktıları Listesi:
        {outcomes_text}
        
        Lütfen en uygun çıktının ID'sini, güven skorunu (0-1 arası) ve kısa gerekçesini JSON olarak dön:
        {{"outcome_id": ..., "score": ..., "reason": "..."}}
        """
        return self._generate(prompt)

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
        
        prompt = f"""
        Aşağıdaki öğrenme çıktısına (kazanıma) ve zorluk seviyesine uygun, {count_str}profesyonel sınav sorusu üret.
        
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
        {format_str}
        """
        return self._generate(prompt)

    def suggest_distractors(self, stem, correct_answer):
        prompt = f"""
        Aşağıdaki soru kökü ve doğru cevap için 3 adet mantıklı çeldirici (yanlış şık) üret.
        
        Soru: {stem}
        Doğru Cevap: {correct_answer}
        
        Lütfen SADECE şu formatta bir JSON listesi dön:
        ["Çeldirici 1", "Çeldirici 2", "Çeldirici 3"]
        """
        return self._generate(prompt)

    def generate_variation(self, item_stem, choices):
        prompt = f"""
        Aşağıdaki sınav sorusunun anlamsal olarak benzer ancak farklı bir versiyonunu üret (sayıları veya örnekleri değiştirerek).
        
        Orijinal Soru: {item_stem}
        Orijinal Şıklar: {choices}
        
        Lütfen cevabı SADECE aşağıdaki JSON formatında dön:
        {{
            "stem": "Yeni soru kökü",
            "choices": [
                {{"label": "A", "text": "Yeni Seçenek A"}},
                ...
            ],
            "correct_answer": "..."
        }}
        """
        return self._generate(prompt)

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
            return None


def get_llm_client():
    # Şimdilik varsayılan olarak Gemini dönüyoruz.
    return GeminiClient()
