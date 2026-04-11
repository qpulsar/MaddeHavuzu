"""
Parsing orchestration service.
Handles the complete workflow of parsing a file and storing results.
"""
from django.utils import timezone
from grading.models import UploadSession, StudentResult, ParsingError, ProcessingStatus, FileFormatConfig
from grading.parsers import ConfigurableParser
from grading.services.grading import GradingService
from grading.utils import decode_content


class ParsingService:
    """
    Orchestrates the complete file processing workflow.
    """
    
    def process_upload(self, upload_session: UploadSession) -> bool:
        """
        Process an uploaded file.
        
        Args:
            upload_session: UploadSession instance to process
            
        Returns:
            True if processing succeeded, False otherwise
        """
        try:
            # Update status
            upload_session.processing_status = ProcessingStatus.PROCESSING
            upload_session.save()
            
            # Get file format config
            file_format = upload_session.file_format
            if not file_format:
                # Try to get default format
                file_format = FileFormatConfig.objects.filter(is_default=True, is_active=True).first()
                if not file_format:
                    file_format = FileFormatConfig.objects.filter(is_active=True).first()
            
            if not file_format:
                raise ValueError("Dosya formatı bulunamadı. Lütfen admin panelinden bir format tanımlayın.")
            
            # Read file content
            upload_session.uploaded_file.seek(0)
            file_bytes = upload_session.uploaded_file.read()
            file_content = decode_content(file_bytes)
            
            # Parse file
            parser = ConfigurableParser(file_format)
            parsed_data = parser.parse(file_content)
            
            # Answer key determination
            answer_key = None
            if parsed_data.has_key:
                if parsed_data.has_multiple_keys:
                    raise ValueError(
                        f"Birden fazla cevap anahtarı bulundu ({len(parsed_data.keys)} adet). "
                        "Lütfen dosyada yalnızca bir anahtar satırı olduğundan emin olun."
                    )
                answer_key = parsed_data.primary_key.answers
            elif upload_session.test_form:
                # Dosyada yoksa ama sınav formu bağlıysa pool'dan üret
                try:
                    from itempool.services.answer_key import generate_answer_key_from_form
                    answer_key = generate_answer_key_from_form(upload_session.test_form)
                except Exception as e:
                    raise ValueError(f"Sınav formu üzerinden cevap anahtarı üretilemedi: {e}")
            
            if not answer_key:
                raise ValueError(
                    f"Cevap anahtarı bulunamadı. Dosyada '{file_format.key_identifier}' ifadesini içeren bir satır "
                    "veya seçili bir sınav formu gereklidir."
                )
            
            # Update question count if it came from the pool (parser sets it only if has_key)
            if not parsed_data.has_key:
                parsed_data.question_count = len(answer_key)
            
            # Initialize grading service with format config
            grading_service = GradingService(
                valid_options=file_format.valid_options,
                blank_markers=file_format.blank_markers,
                correct_points=float(upload_session.points_per_question),
                wrong_to_correct_ratio=upload_session.wrong_to_correct_ratio or 0
            )
            
            # Grade and save student results
            for student in parsed_data.students:
                grading_result = grading_service.grade_student(student.answers, answer_key)
                
                StudentResult.objects.create(
                    upload_session=upload_session,
                    student_no=student.student_no,
                    student_name=student.student_name,
                    booklet=student.booklet,
                    answers_raw=student.answers,
                    row_number_in_file=student.row_number,
                    correct_count=grading_result.correct_count,
                    wrong_count=grading_result.wrong_count,
                    blank_count=grading_result.blank_count,
                    invalid_count=grading_result.invalid_count,
                    net=grading_result.net,
                    score=grading_result.score,
                    detailed_results=grading_result.detailed_results,
                )
            
            # Save parsing errors
            for error in parsed_data.errors:
                ParsingError.objects.create(
                    upload_session=upload_session,
                    row_number=error.row_number,
                    raw_line=error.raw_line,
                    message=error.message,
                )
            
            # Update session with results
            upload_session.question_count = parsed_data.question_count
            upload_session.student_count = len(parsed_data.students)
            upload_session.error_count = len(parsed_data.errors)
            upload_session.has_multiple_keys = parsed_data.has_multiple_keys
            upload_session.answer_key = answer_key # Save the answer key for analysis
            upload_session.processing_status = ProcessingStatus.PROCESSED
            upload_session.processed_at = timezone.now()
            upload_session.save()
            
            return True
            
        except Exception as e:
            # Mark as failed
            upload_session.processing_status = ProcessingStatus.FAILED
            upload_session.error_summary = str(e)
            upload_session.save()
            return False
            
    def recalculate_scores(self, upload_session: UploadSession):
        """
        Recalculate scores for all results in a session.
        Useful when the wrong_to_correct_ratio is changed.
        """
        file_format = upload_session.file_format
        if not file_format:
            file_format = FileFormatConfig.objects.filter(is_default=True).first()
            
        grading_service = GradingService(
            valid_options=file_format.valid_options,
            blank_markers=file_format.blank_markers,
            correct_points=float(upload_session.points_per_question),
            wrong_to_correct_ratio=upload_session.wrong_to_correct_ratio or 0
        )
        
        answer_key = upload_session.answer_key
        
        results = upload_session.results.all()
        for result in results:
            if not answer_key:
                # Fallback: Calculate from existing counts if key is missing
                net, score = grading_service.calculate_score_from_counts(
                    result.correct_count, result.wrong_count, result.blank_count
                )
                result.net = net
                result.score = score
            else:
                # Re-grade if key is available
                grading_result = grading_service.grade_student(result.answers_raw, answer_key)
                result.net = grading_result.net
                result.score = grading_result.score
                # Note: original counts (correct_count, etc.) are NOT updated here 
                # to prevent destructive changes if something is wrong with the re-grading
            
            result.save()
        
        return True
