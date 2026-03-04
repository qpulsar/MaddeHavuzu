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


def get_llm_client():
    # Şimdilik varsayılan olarak Gemini dönüyoruz.
    return GeminiClient()
