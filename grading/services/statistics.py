
import statistics
from typing import List, Dict, Any
from django.db.models import QuerySet

class StatisticsService:
    """
    Central service for calculating exam statistics and item analysis.
    """
    
    def calculate_session_stats(self, session) -> Dict[str, Any]:
        """
        Calculate all stats for a given UploadSession.
        """
        results = session.results.all()
        scores = [float(r.score) for r in results if r.score is not None]
        
        if not scores:
            return {}
            
        # Basic stats
        mean = sum(scores) / len(scores)
        median = statistics.median(scores)
        std_dev = statistics.stdev(scores) if len(scores) > 1 else 0
        
        # Histogram data
        q_count = session.question_count or 0
        bins = [0] * (q_count + 1)
        for result in results:
            if result.correct_count is not None and 0 <= result.correct_count <= q_count:
                bins[result.correct_count] += 1
        
        # Interpretations
        skewness = 3 * (mean - median) / std_dev if std_dev > 0 else 0
        dist_interpretation, interpretation_type = self._get_distribution_interpretation(skewness)
        
        variation_coeff = (std_dev / mean) * 100 if mean > 0 else 0
        group_structure = self._get_group_structure(variation_coeff)
        
        # Item Analysis
        item_analysis = self._calculate_item_analysis(session, results)
        
        return {
            'mean': mean,
            'median': median,
            'std_dev': std_dev,
            'skewness': skewness,
            'variation_coeff': variation_coeff,
            'dist_interpretation': dist_interpretation,
            'interpretation_type': interpretation_type,
            'group_structure': group_structure,
            'histogram_bins': bins,
            'item_analysis': item_analysis,
            'student_count': len(results),
            'question_count': q_count
        }

    def _get_distribution_interpretation(self, skewness: float) -> tuple:
        if skewness > 0.5:
            return ("Ölçme sonuçları sağa çarpık bir dağılım sergilemektedir. Bu durum, sınav sorularının hedef kitlenin üzerinde bir güçlüğe sahip olduğunu veya ilgili kazanımların henüz beklenen düzeyde içselleştirilmediğini göstermektedir.", "danger")
        elif skewness < -0.5:
            return ("Ölçme sonuçları sola çarpık bir dağılım sergilemektedir. Bu veriler, sınıf genelinde başarının yüksek olduğunu, öğretim süreçlerinin verimli geçtiğini veya sınavın kapsam geçerliliği dahilinde nispeten kolay algılandığını ifade eder.", "success")
        else:
            return ("Ölçme sonuçları normal (simetrik) dağılıma yakın bir seyir izlemektedir. Bu durum, ölçme aracının grup seviyesine uygun olduğunu ve öğrenci grubunun heterojen yapısını başarılı bir şekilde yansıttığını gösterir.", "info")

    def _get_group_structure(self, variation_coeff: float) -> str:
        if variation_coeff < 20:
            return "Grup, başarı düzeyi açısından homojen bir yapı sergilemektedir. Öğrenciler arası öğrenme farklılıkları düşüktür."
        elif variation_coeff > 35:
            return "Grup, başarı düzeyi açısından oldukça heterojen bir yapıdadır. Bireysel öğrenme hızları ve hazırbulunuşluk düzeyleri arasında belirgin farklar mevcuttur."
        else:
            return "Grup, orta düzeyde bir dağılım sergilemektedir; standart bir sınıf heterojenliğine sahiptir."

    def _calculate_item_analysis(self, session, results: List[Any]) -> List[Dict[str, Any]]:
        item_analysis = []
        answer_key = session.answer_key or ""
        valid_options = session.file_format.valid_options if session.file_format else "ABCDE"
        q_count = session.question_count or 0
        
        # Groups for discrimination
        sorted_results = sorted(results, key=lambda x: x.score if x.score is not None else 0, reverse=True)
        group_size = int(len(sorted_results) * 0.27) or 1
        top_group = sorted_results[:group_size]
        bottom_group = sorted_results[-group_size:]
        
        for i in range(q_count):
            correct_ans = answer_key[i] if i < len(answer_key) else "?"
            
            option_counts = {opt: 0 for opt in valid_options}
            option_counts['Boş/Geçersiz'] = 0
            
            correct_in_all = 0
            for r in results:
                ans = r.answers_raw[i] if i < len(r.answers_raw) else " "
                if ans == correct_ans:
                    correct_in_all += 1
                
                if ans in option_counts:
                    option_counts[ans] += 1
                else:
                    option_counts['Boş/Geçersiz'] += 1
            
            p = correct_in_all / len(results) if len(results) > 0 else 0
            
            correct_in_top = sum(1 for r in top_group if i < len(r.answers_raw) and r.answers_raw[i] == correct_ans)
            correct_in_bottom = sum(1 for r in bottom_group if i < len(r.answers_raw) and r.answers_raw[i] == correct_ans)
            r_index = (correct_in_top - correct_in_bottom) / group_size if group_size > 0 else 0
            
            item_analysis.append({
                'question_number': i + 1,
                'correct_answer': correct_ans,
                'p': p,
                'r': r_index,
                'option_counts': option_counts,
                'difficulty': self._get_p_comment(p),
                'discrimination': self._get_r_comment(r_index)
            })
            
        return item_analysis

    def _get_p_comment(self, p: float) -> str:
        if p > 0.85: return "Çok Kolay"
        elif p < 0.15: return "Çok Zor"
        else: return "Orta Güçlük"

    def _get_r_comment(self, r: float) -> str:
        if r < 0.19: return "Ayırt Edici Değil"
        elif r < 0.29: return "Zayıf Ayırt Edici"
        elif r < 0.39: return "İyi Ayırt Edici"
        else: return "Çok İyi Ayırt Edici"

    def calculate_kr20(self, session) -> Dict[str, Any]:
        """
        Calculate KR-20 (Kuder-Richardson 20) reliability coefficient.
        KR-20 is used for dichotomously scored items (correct/incorrect).
        
        Formula: KR20 = (k / (k-1)) * (1 - Σpq / σ²)
        where:
            k = number of items
            p = proportion of correct responses for each item
            q = 1 - p
            σ² = variance of total scores
        """
        results = session.results.all()
        answer_key = session.answer_key or ""
        q_count = session.question_count or 0
        
        if not results or q_count < 2:
            return {}
        
        # Create score matrix: 1 for correct, 0 for incorrect
        score_matrix = []
        total_scores = []
        
        for r in results:
            item_scores = []
            for i in range(q_count):
                correct_ans = answer_key[i] if i < len(answer_key) else "?"
                student_ans = r.answers_raw[i] if i < len(r.answers_raw) else " "
                item_scores.append(1 if student_ans == correct_ans else 0)
            score_matrix.append(item_scores)
            total_scores.append(sum(item_scores))
        
        n = len(results)  # number of students
        k = q_count       # number of items
        
        # Calculate p and q for each item
        item_stats = []
        sum_pq = 0
        
        for i in range(k):
            correct_count = sum(scores[i] for scores in score_matrix)
            p = correct_count / n
            q = 1 - p
            pq = p * q
            sum_pq += pq
            item_stats.append({
                'item_number': i + 1,
                'p': round(p, 3),
                'q': round(q, 3),
                'pq': round(pq, 4),
                'correct_count': correct_count,
                'contribution': round(pq, 4)  # contribution to reliability
            })
        
        # Calculate variance of total scores
        mean_score = sum(total_scores) / n
        variance = sum((score - mean_score) ** 2 for score in total_scores) / n
        
        # Calculate KR-20
        if variance == 0:
            kr20 = 0
        else:
            kr20 = (k / (k - 1)) * (1 - sum_pq / variance)
        
        # Interpretation
        kr20_interpretation, interpretation_type = self._get_kr20_interpretation(kr20)
        
        return {
            'kr20': round(kr20, 4),
            'k': k,
            'n': n,
            'sum_pq': round(sum_pq, 4),
            'variance': round(variance, 4),
            'mean_score': round(mean_score, 2),
            'interpretation': kr20_interpretation,
            'interpretation_type': interpretation_type,
            'item_stats': item_stats
        }
    
    def _get_kr20_interpretation(self, kr20: float) -> tuple:
        """Return interpretation of KR-20 coefficient."""
        if kr20 >= 0.90:
            return ("Mükemmel düzeyde güvenirlik. Test, bireysel değerlendirmeler için oldukça uygun.", "success")
        elif kr20 >= 0.80:
            return ("İyi düzeyde güvenirlik. Test, grup karşılaştırmaları ve bireysel değerlendirmeler için uygundur.", "success")
        elif kr20 >= 0.70:
            return ("Kabul edilebilir düzeyde güvenirlik. Test, araştırma amaçlı kullanıma uygundur.", "info")
        elif kr20 >= 0.60:
            return ("Düşük güvenirlik. Test sonuçları dikkatli yorumlanmalıdır.", "warning")
        elif kr20 >= 0.50:
            return ("Zayıf güvenirlik. Testin revize edilmesi önerilir.", "danger")
        else:
            return ("Çok düşük güvenirlik. Test güvenilir değildir ve kullanılması önerilmez.", "danger")

    def calculate_cronbach_alpha(self, session) -> Dict[str, Any]:
        """
        Calculate Cronbach's Alpha (α) reliability coefficient.
        Cronbach's Alpha is a more general form of KR-20.
        For dichotomously scored items (0/1), it gives nearly identical results to KR-20.
        
        Formula: α = (k / (k-1)) * (1 - Σσ²ᵢ / σ²ₜ)
        where:
            k = number of items
            σ²ᵢ = variance of each item
            σ²ₜ = variance of total scores
        """
        results = session.results.all()
        answer_key = session.answer_key or ""
        q_count = session.question_count or 0
        
        if not results or q_count < 2:
            return {}
        
        # Create score matrix: 1 for correct, 0 for incorrect
        score_matrix = []
        total_scores = []
        
        for r in results:
            item_scores = []
            for i in range(q_count):
                correct_ans = answer_key[i] if i < len(answer_key) else "?"
                student_ans = r.answers_raw[i] if i < len(r.answers_raw) else " "
                item_scores.append(1 if student_ans == correct_ans else 0)
            score_matrix.append(item_scores)
            total_scores.append(sum(item_scores))
        
        n = len(results)  # number of students
        k = q_count       # number of items
        
        # Calculate variance of each item and sum of item variances
        item_stats = []
        sum_item_variance = 0
        
        for i in range(k):
            item_scores = [scores[i] for scores in score_matrix]
            item_mean = sum(item_scores) / n
            item_variance = sum((score - item_mean) ** 2 for score in item_scores) / n
            sum_item_variance += item_variance
            
            correct_count = sum(item_scores)
            p = correct_count / n
            
            item_stats.append({
                'item_number': i + 1,
                'mean': round(item_mean, 3),
                'variance': round(item_variance, 4),
                'p': round(p, 3),
                'correct_count': correct_count
            })
        
        # Calculate variance of total scores
        mean_score = sum(total_scores) / n
        total_variance = sum((score - mean_score) ** 2 for score in total_scores) / n
        
        # Calculate Cronbach's Alpha
        if total_variance == 0:
            alpha = 0
        else:
            alpha = (k / (k - 1)) * (1 - sum_item_variance / total_variance)
        
        # Interpretation (same scale as KR-20)
        alpha_interpretation, interpretation_type = self._get_alpha_interpretation(alpha)
        
        return {
            'alpha': round(alpha, 4),
            'k': k,
            'n': n,
            'sum_item_variance': round(sum_item_variance, 4),
            'total_variance': round(total_variance, 4),
            'mean_score': round(mean_score, 2),
            'interpretation': alpha_interpretation,
            'interpretation_type': interpretation_type,
            'item_stats': item_stats
        }
    
    def _get_alpha_interpretation(self, alpha: float) -> tuple:
        """Return interpretation of Cronbach's Alpha coefficient."""
        if alpha >= 0.90:
            return ("Mükemmel düzeyde iç tutarlılık. Test, bireysel değerlendirmeler için oldukça güvenilir.", "success")
        elif alpha >= 0.80:
            return ("İyi düzeyde iç tutarlılık. Test, grup ve bireysel ölçümler için güvenilirdir.", "success")
        elif alpha >= 0.70:
            return ("Kabul edilebilir düzeyde iç tutarlılık. Test, araştırma amaçlı kullanıma uygundur.", "info")
        elif alpha >= 0.60:
            return ("Düşük iç tutarlılık. Sonuçlar dikkatli yorumlanmalıdır.", "warning")
        elif alpha >= 0.50:
            return ("Zayıf iç tutarlılık. Testin gözden geçirilmesi önerilir.", "danger")
        else:
            return ("Çok düşük iç tutarlılık. Test güvenilir değildir.", "danger")

