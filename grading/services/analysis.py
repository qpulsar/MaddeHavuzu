
from collections import defaultdict
import statistics
from typing import List, Dict, Any, Tuple
from django.db.models import QuerySet
from grading.models import UploadSession, StudentResult

class CheatingAnalysisService:
    """
    Service for analyzing student results to detect potential cheating
    based on wrong answer similarities and other patterns.
    """
    
    def __init__(self, session: UploadSession):
        self.session = session
        self.results = list(session.results.all())
        self.question_count = session.question_count
        self.answer_key = session.answer_key
        
    def analyze(self, exclude_top_percent: float = 0, 
                same_wrong_weight: float = 1.0,
                discrimination_weight_factor: float = 0.0) -> Dict[str, Any]:
        """
        Perform the full cheating analysis.
        
        Args:
            exclude_top_percent: Percentage of top scoring students to exclude (0-100)
            same_wrong_weight: Weight multiplier for same wrong answers
            discrimination_weight_factor: Multiplier for item discrimination (r)
            
        Returns:
            Dictionary containing analysis results
        """
        # Filter students (exclude top % if requested)
        sorted_results = sorted(self.results, key=lambda x: x.score or 0, reverse=True)
        if exclude_top_percent > 0:
            exclude_count = int(len(sorted_results) * (exclude_top_percent / 100))
            active_results = sorted_results[exclude_count:]
        else:
            active_results = sorted_results
            
        if len(active_results) < 2:
            return {'error': 'Yeterli öğrenci verisi yok.'}
            
        # 1. Calculate item discrimination (r) if needed for weighting
        item_discrimination = {}
        if discrimination_weight_factor > 0:
            item_discrimination = self._calculate_item_discrimination(self.results) # Use all results for r calc
            
        # 2. Pairwise comparison
        pairs = []
        scores = []
        
        n = len(active_results)
        for i in range(n):
            for j in range(i + 1, n):
                s1 = active_results[i]
                s2 = active_results[j]
                
                # Skip if books are different (optional, but requested logic implies analyzing copy)
                # Usually copying happens regardless of booklet, but detecting it is harder if booklets are different
                # For now, we compare everyone with everyone as raw answers are what matters.
                # Assuming raw answers are normalized to a single key or we are just comparing raw input.
                # If booklets exist, "answers_raw" might need mapping. 
                # HOWEVER, in this system, it seems answers_raw is directly compared to the key.
                # We will compare answers_raw directly.
                
                similarity_score, details = self._compare_students(
                    s1, s2, 
                    same_wrong_weight, 
                    discrimination_weight_factor, 
                    item_discrimination
                )
                
                pairs.append({
                    's1': s1,
                    's2': s2,
                    'score': similarity_score,
                    'details': details
                })
                scores.append(similarity_score)
                
        # 3. Statistical Analysis of Scores
        if not scores:
             return {'error': 'Karşılaştırılacak veri yok.'}
             
        mean_score = statistics.mean(scores)
        stdev_score = statistics.stdev(scores) if len(scores) > 1 else 0
        
        # 4. Identify Risky Pairs
        risky_pairs = []
        for p in pairs:
            # Z-score calculation
            z_score = (p['score'] - mean_score) / stdev_score if stdev_score > 0 else 0
            
            risk_level = "Düşük"
            if z_score > 3.0:
                risk_level = "Yüksek"
            elif z_score > 2.0:
                risk_level = "Orta"
            
            p['z_score'] = z_score
            p['risk_level'] = risk_level
            
            if risk_level != "Düşük":
                risky_pairs.append(p)
                
        # Sort risky pairs by score desc
        risky_pairs.sort(key=lambda x: x['score'], reverse=True)
        
        # 5. Prepare Output
        return {
            'risky_pairs': risky_pairs,
            'stats': {
                'mean': mean_score,
                'stdev': stdev_score,
                'pair_count': len(pairs)
            },
            'parameters': {
                'exclude_top_percent': exclude_top_percent,
                'same_wrong_weight': same_wrong_weight,
                'discrimination_weight_factor': discrimination_weight_factor
            }
        }
        
    def _compare_students(self, s1: StudentResult, s2: StudentResult, 
                          same_wrong_weight: float, 
                          discrimination_weight_factor: float,
                          item_discrimination: Dict[int, float]) -> Tuple[float, Dict]:
        """Compare two students and calculate similarity score."""
        score = 0.0
        matches = 0
        same_wrongs = 0
        
        a1 = s1.answers_raw
        a2 = s2.answers_raw
        min_len = min(len(a1), len(a2), len(self.answer_key))
        
        for k in range(min_len):
            char1 = a1[k]
            char2 = a2[k]
            key_char = self.answer_key[k]
            
            # Weighted logic
            weight = 1.0
            
            # Add discrimination weight if enabled
            if discrimination_weight_factor > 0:
                r_val = item_discrimination.get(k, 0)
                # Higher discrimination items should carry more weight if copied?
                # Actually, usually "hard" questions (low p) or highly discriminating questions
                # are stronger indicators. The user asked for "Distinction high items weight".
                # If r is high, it distinguishes well. Copied answers on these might be significant.
                # We add r * factor to base weight.
                if r_val > 0:
                    weight += (r_val * discrimination_weight_factor)
            
            if char1 == char2 and char1.strip(): # Match and not empty
                matches += 1
                
                is_wrong = (char1 != key_char)
                
                if is_wrong:
                    # Same wrong answer
                    score += (weight * same_wrong_weight)
                    same_wrongs += 1
                else:
                    # Same correct answer (less weight usually, but let's keep base)
                    # Often in copy analysis, correct answers are less suspicious than idiosyncratic wrongs.
                    # But we'll just use base weight for corrects.
                    score += weight
                    
        return score, {
            'matches': matches,
            'same_wrongs': same_wrongs,
            'total_q': min_len
        }

    def _calculate_item_discrimination(self, results) -> Dict[int, float]:
        """Calculates discrimination index (r) for each item."""
        # Simple upper-lower group method
        sorted_res = sorted(results, key=lambda x: x.score or 0, reverse=True)
        n = len(sorted_res)
        group_size = int(n * 0.27) or 1
        
        top = sorted_res[:group_size]
        bottom = sorted_res[-group_size:]
        
        discriminations = {}
        
        # We need to loop questions
        slen = len(self.answer_key)
        for i in range(slen):
            key_char = self.answer_key[i]
            
            top_correct = sum(1 for s in top if i < len(s.answers_raw) and s.answers_raw[i] == key_char)
            bottom_correct = sum(1 for s in bottom if i < len(s.answers_raw) and s.answers_raw[i] == key_char)
            
            # r = (Ru - Ra) / GroupSize
            r = (top_correct - bottom_correct) / group_size
            discriminations[i] = r
            
        return discriminations
