import numpy as np
from itempool.models import Item, ItemEmbedding, ItemInstance
from .llm_client import get_llm_client

class SimilarityService:
    @staticmethod
    def cosine_similarity(v1, v2):
        v1 = np.array(v1)
        v2 = np.array(v2)
        dot_product = np.dot(v1, v2)
        norm_v1 = np.linalg.norm(v1)
        norm_v2 = np.linalg.norm(v2)
        if norm_v1 == 0 or norm_v2 == 0:
            return 0.0
        return dot_product / (norm_v1 * norm_v2)

    @classmethod
    def get_item_text(cls, item):
        """Embedding için madde metnini hazırlar (Kök + Şıklar/Cevap)"""
        text = f"Soru: {item.stem}\n"
        if item.item_type in ['MCQ', 'TF']:
            choices = "\n".join([f"{c.label}: {c.text}" for c in item.choices.all()])
            text += f"Seçenekler:\n{choices}"
        elif item.item_type == 'SHORT_ANSWER':
            text += f"Beklenen Cevap: {item.expected_answer or ''}"
        return text

    @classmethod
    def find_similar_items(cls, query_text, pool_id=None, threshold=0.85, top_n=5):
        client = get_llm_client()
        query_vector = client.get_embedding(query_text)
        if not query_vector:
            return []
            
        # Tüm embedding'leri getir
        embeddings_qs = ItemEmbedding.objects.select_related('item').all()
        
        if pool_id:
            # Sadece belirli bir havuzdaki maddelerle kıyasla
            instance_ids = ItemInstance.objects.filter(pool_id=pool_id).values_list('item_id', flat=True)
            embeddings_qs = embeddings_qs.filter(item_id__in=instance_ids)

        results = []
        for emb in embeddings_qs:
            # JSONField'dan gelen listeyi numpy dizisine çeviriyoruz
            score = cls.cosine_similarity(query_vector, emb.vector)
            if score >= threshold:
                results.append({
                    'item': emb.item,
                    'score': round(score * 100, 1),
                    'label': cls.get_threshold_label(score * 100)
                })
        
        # Skora göre azalan sırala
        results.sort(key=lambda x: x['score'], reverse=True)
        return results[:top_n]

    @staticmethod
    def get_threshold_label(score_percent):
        if score_percent >= 90: return "Mükerrer veya çok yakın"
        if score_percent >= 80: return "Yüksek benzerlik"
        if score_percent >= 70: return "Orta benzerlik / Konu benzeri"
        if score_percent >= 60: return "Düşük benzerlik / İlgili"
        return "Anlamsal fark belirgin"

    @staticmethod
    def calculate_embedding_cost(text_list):
        """Tahmini maliyet hesaplar ($0.01 / 1M token)"""
        total_chars = sum(len(t) for t in text_list)
        # 1 token ~= 4 karakter
        estimated_tokens = total_chars / 4
        cost = (estimated_tokens / 1_000_000) * 0.01
        return {
            'chars': total_chars,
            'tokens': int(estimated_tokens),
            'cost_usd': round(cost, 5),
            'cost_str': f"${cost:.5f}"
        }
