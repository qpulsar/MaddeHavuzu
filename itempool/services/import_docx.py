import re
from docx import Document
from ..models.imports import ImportBatch, DraftItem
from .llm_client import get_llm_client
from django.conf import settings

class DocxImportService:
    """
    Word (.docx) dosyalarını ayrıştırıp taslak madde (DraftItem) olarak kaydeden servis.
    """
    
    # Soru numarası regex (1. 2) 1- 12. vb.)
    QUESTION_RE = re.compile(r'^\s*(\d+)[.)-]\s*(.*)')
    # Şık regex (A) B) A. B- A: vb.)
    CHOICE_RE = re.compile(r'^\s*([A-Ea-e])[\.\)\-:]\s*(.*)')
    # Yan yana şıklar için regex (A. ... B. ... C. ...)
    INLINE_CHOICES_RE = re.compile(r'([A-Ea-e])[\.\)\-:]\s*([^A-Ea-e\.\)\-:]+)')
    # Doğru cevap belirteci (Cevap: A, Cevap=C, Yanıt B, Doğru Cevap: D vb.)
    CORRECT_RE = re.compile(r'(?:Cevap|Yanıt|Key|Doğru Cevap)\s*[:=]\s*([A-Ea-e])', re.IGNORECASE)

    def __init__(self, batch_id, use_ai=False):
        self.batch = ImportBatch.objects.get(id=batch_id)
        self.use_ai = use_ai
        self.llm = get_llm_client() if use_ai else None

    def process(self):
        doc = Document(self.batch.uploaded_file.path)
        
        current_item = None
        last_unmatched_text = ""
        items_count = 0
        
        for para in doc.paragraphs:
            text = para.text.strip()
            if not text:
                continue
            
            q_match = self.QUESTION_RE.match(text)
            c_match = self.CHOICE_RE.match(text)
            ans_match = self.CORRECT_RE.search(text)
            
            if ans_match:
                if current_item:
                    current_item['correct'] = ans_match.group(1).upper()
                continue
                
            if c_match:
                # Satırda birden fazla şık var mı kontrol et (Ör: A. X B. Y C. Z D. T)
                inline_matches = list(self.INLINE_CHOICES_RE.finditer(text))
                if len(inline_matches) > 1:
                    if not current_item:
                        current_item = {
                            'stem': last_unmatched_text.strip() or "Soru Kökü Eksik",
                            'choices': [],
                            'correct': None
                        }
                        last_unmatched_text = ""
                    for m in inline_matches:
                        current_item['choices'].append({
                            'label': m.group(1).upper(),
                            'text': m.group(2).strip()
                        })
                else:
                    label = c_match.group(1).upper()
                    choice_text = c_match.group(2)
                    
                    if not current_item:
                        current_item = {
                            'stem': last_unmatched_text.strip() or "Soru Kökü Eksik",
                            'choices': [],
                            'correct': None
                        }
                        last_unmatched_text = ""
                    
                    current_item['choices'].append({
                        'label': label,
                        'text': choice_text
                    })
            elif q_match:
                if current_item:
                    self._save_draft(current_item)
                    items_count += 1
                
                # Öncüllü sorular için (I., II. vb.) soru numarası gelmeden önceki metni soru kökünün başına ekle
                full_stem = q_match.group(2)
                if last_unmatched_text:
                    full_stem = f"{last_unmatched_text.strip()}\n{full_stem}"
                
                current_item = {
                    'stem': full_stem.strip(),
                    'choices': [],
                    'correct': None
                }
                last_unmatched_text = ""
            else:
                # Numarasız metin
                # Eğer zaten bir sorumuz varsa ve şıkları eklenmişse, bu yeni bir sorunun başlangıcıdır!
                if current_item and current_item['choices']:
                    self._save_draft(current_item)
                    items_count += 1
                    current_item = None
                
                if current_item:
                    current_item['stem'] += "\n" + text
                else:
                    if last_unmatched_text:
                        last_unmatched_text += "\n" + text
                    else:
                        last_unmatched_text = text

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
