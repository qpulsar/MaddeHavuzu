import re
from docx import Document
from ..models.imports import ImportBatch, DraftItem
from .llm_client import get_llm_client
from django.conf import settings

class DocxImportService:
    """
    Word (.docx) dosyalarını ayrıştırıp taslak madde (DraftItem) olarak kaydeden servis.
    """
    
    # Soru numarası regex (1. 2) 1- vb.)
    QUESTION_RE = re.compile(r'^(\d+)[.)-]\s*(.*)')
    # Şık regex (A) B) A. B. vb.)
    CHOICE_RE = re.compile(r'^([A-Ea-e])[.)]\s*(.*)')
    # Doğru cevap belirteci (Cevap: A, Yanıt B vb.)
    CORRECT_RE = re.compile(r'^(Cevap|Yanıt|Key):\s*([A-Ea-e])', re.IGNORECASE)

    def __init__(self, batch_id, use_ai=False):
        self.batch = ImportBatch.objects.get(id=batch_id)
        self.use_ai = use_ai
        self.llm = get_llm_client() if use_ai else None

    def process(self):
        doc = Document(self.batch.uploaded_file.path)
        
        current_item = None
        items_count = 0
        
        for para in doc.paragraphs:
            text = para.text.strip()
            
            # Word'ün kendi numaralandırma sistemi var mı kontrol et
            is_numbered = self._is_numbered(para)
            
            if not text and not is_numbered:
                continue
            
            # Regex kontrolleri
            q_match = self.QUESTION_RE.match(text)
            c_match = self.CHOICE_RE.match(text)
            ans_match = self.CORRECT_RE.match(text)

            # Karar değişkenleri
            is_new_question = False
            is_choice = False
            
            if c_match:
                # Metin A), B) gibi başlıyorsa seviye ne olursa olsun şıktır
                is_choice = True
            elif q_match:
                # Metin 1., 2. gibi başlıyorsa seviye ne olursa olsun sorudur
                is_new_question = True
            elif is_numbered:
                # Metinde açıkça 1. veya A) yok ama Word liste diyor
                level = self._get_num_level(para)
                if level == 0:
                    is_new_question = True
                else:
                    is_choice = True
            
            # Doğru cevap kontrolü (En yüksek öncelik değil ama ayrık olmalı)
            if ans_match and current_item:
                current_item['correct'] = ans_match.group(2).upper()
                continue

            # Uygulama: Soru başlangıcı
            if is_new_question:
                if current_item:
                    self._save_draft(current_item)
                    items_count += 1
                
                stem_text = q_match.group(2) if q_match else text
                current_item = {
                    'stem': stem_text,
                    'choices': [],
                    'correct': None
                }
                continue
            
            # Uygulama: Seçenek ekleme
            if is_choice and current_item:
                label = c_match.group(1).upper() if c_match else self._predict_next_label(current_item['choices'])
                choice_text = c_match.group(2) if c_match else text
                
                current_item['choices'].append({
                    'label': label,
                    'text': choice_text
                })
                continue
            
            # Eğer yukarıdakiler değilse ve current_item varsa, köke ekleme yap (çok satırlı soru kökü)
            if current_item and not current_item['choices']:
                current_item['stem'] += "\n" + text

        # Son soruyu kaydet
        if current_item:
            self._save_draft(current_item)
            items_count += 1
            
        self.batch.item_count = items_count
        self.batch.status = ImportBatch.Status.COMPLETED
        self.batch.save()
        
        return items_count

    def _save_draft(self, item_data):
        manual_review = False
        review_note = ""
        
        if not item_data['choices']:
            manual_review = True
            review_note += "Şık bulunamadı. "
        
        if not item_data['correct']:
            manual_review = True
            review_note += "Doğru cevap bulunamadı. "

        DraftItem.objects.create(
            batch=self.batch,
            stem=item_data['stem'],
            choices_json=item_data['choices'],
            correct_answer=item_data['correct'],
            manual_review=manual_review,
            review_note=review_note.strip(),
            ai_suggestions=self._get_ai_suggestions(item_data) if self.use_ai else None
        )

    def _get_ai_suggestions(self, item_data):
        if not self.llm: return None
        # Basit bir çağrı örneği
        try:
            res = self.llm.suggest_improvements(item_data['stem'], str(item_data['choices']))
            return {"improvement": res}
        except:
            return None

    def _is_numbered(self, para):
        """Paragrafın Word numbering sistemine dahil olup olmadığını kontrol eder."""
        return para._element.xpath('.//w:numPr') != []

    def _get_num_level(self, para):
        """Liste seviyesini döner (0 genellikle ana seviye/soru, >0 şıklar)."""
        try:
            return int(para._element.xpath('.//w:ilvl')[0].get('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val'))
        except:
            return 0

    def _predict_next_label(self, existing_choices):
        """Sıradaki şık etiketini tahmin eder (A, B, C...)."""
        labels = "ABCDE"
        count = len(existing_choices)
        return labels[count] if count < len(labels) else "?"
