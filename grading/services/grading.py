"""
Grading service for evaluating student answers.
"""
from dataclasses import dataclass
from typing import List


@dataclass
class GradingResult:
    """Result of grading a single student."""
    correct_count: int = 0
    wrong_count: int = 0
    blank_count: int = 0
    invalid_count: int = 0
    net: float = 0.0
    score: float = 0.0
    detailed_results: str = ''  # D/Y/B/G for each question


class GradingService:
    """
    Service for grading student answers against an answer key.
    """
    
    def __init__(
        self,
        valid_options: str = 'ABCDE',
        blank_markers: str = '-* .',
        correct_points: float = 1.0,
        wrong_points: float = 0.0,
        blank_points: float = 0.0,
        wrong_to_correct_ratio: int = 0
    ):
        """
        Initialize grading service with configuration.
        
        Args:
            valid_options: Valid answer characters (e.g., 'ABCDE')
            blank_markers: Characters representing blank answers
            correct_points: Points for correct answer
            wrong_points: Points for wrong answer (usually 0 or negative)
            blank_points: Points for blank answer
            wrong_to_correct_ratio: Number of wrong answers that cancel one correct answer (e.g., 4)
        """
        self.valid_options = set(valid_options.upper())
        self.blank_markers = set(blank_markers)
        self.correct_points = correct_points
        self.wrong_points = wrong_points
        self.blank_points = blank_points
        self.wrong_to_correct_ratio = wrong_to_correct_ratio
    
    def grade_student(self, student_answers: str, answer_key: str) -> GradingResult:
        """
        Grade a student's answers against the answer key.
        
        Args:
            student_answers: Student's answer string
            answer_key: Correct answer string
            
        Returns:
            GradingResult with counts and score
        """
        result = GradingResult()
        detailed = []
        
        # Pad answers if shorter than key
        key_length = len(answer_key)
        student_answers = student_answers.ljust(key_length)
        
        for i, (student_ans, correct_ans) in enumerate(zip(student_answers, answer_key)):
            student_ans = student_ans.upper()
            correct_ans = correct_ans.upper()
            
            if self._is_blank(student_ans):
                result.blank_count += 1
                detailed.append('B')
            elif self._is_invalid(student_ans):
                result.invalid_count += 1
                detailed.append('G')  # Geçersiz
            elif student_ans == correct_ans:
                result.correct_count += 1
                detailed.append('D')  # Doğru
            else:
                result.wrong_count += 1
                detailed.append('Y')  # Yanlış
        
        # Calculate score and net
        if self.wrong_to_correct_ratio > 0:
            # Net calculation: correct - (wrong / ratio)
            result.net = result.correct_count - (result.wrong_count / self.wrong_to_correct_ratio)
            result.score = result.net * self.correct_points
        else:
            result.net = float(result.correct_count)
            result.score = (
                result.correct_count * self.correct_points +
                result.wrong_count * self.wrong_points +
                result.blank_count * self.blank_points
            )
        
        result.detailed_results = ''.join(detailed)
        return result
    
    def _is_blank(self, answer: str) -> bool:
        """Check if answer is blank."""
        return answer in self.blank_markers or answer == '' or answer == ' '
    
    def _is_invalid(self, answer: str) -> bool:
        """Check if answer is invalid (not a valid option and not blank)."""
        if self._is_blank(answer):
            return False
        return answer not in self.valid_options
    
    def calculate_score_from_counts(self, correct_count: int, wrong_count: int, blank_count: int) -> tuple:
        """Calculate net and score from existing counts without re-grading."""
        if self.wrong_to_correct_ratio > 0:
            net = float(correct_count) - (float(wrong_count) / self.wrong_to_correct_ratio)
            score = net * self.correct_points
        else:
            net = float(correct_count)
            score = (
                correct_count * self.correct_points +
                wrong_count * self.wrong_points +
                blank_count * self.blank_points
            )
        return net, score

    def grade_all(self, students: List[dict], answer_key: str) -> List[dict]:
        """
        Grade multiple students.
        
        Args:
            students: List of dicts with 'answers' key
            answer_key: Correct answer string
            
        Returns:
            List of dicts with grading results added
        """
        results = []
        for student in students:
            grading = self.grade_student(student['answers'], answer_key)
            student_result = {
                **student,
                'correct_count': grading.correct_count,
                'wrong_count': grading.wrong_count,
                'blank_count': grading.blank_count,
                'invalid_count': grading.invalid_count,
                'score': grading.score,
                'detailed_results': grading.detailed_results,
            }
            results.append(student_result)
        return results
