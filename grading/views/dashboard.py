"""
Dashboard and main application views.
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.http import HttpResponse
from django.views import View
from django.core.paginator import Paginator

from django.db.models import Avg, StdDev
import math
import statistics
from grading.models import UploadSession, FileFormatConfig, ProcessingStatus, StudentResult
from grading.services.parsing import ParsingService
from grading.services.export_xlsx import ExcelExportService
from grading.services.statistics import StatisticsService
from grading.utils import sanitize_filename
from itempool.models import ItemPool, ItemInstance, ItemAuditLog


class DashboardView(LoginRequiredMixin, View):
    """Main dashboard showing upload history."""
    
    def get(self, request):
        user = request.user
        # Get user's upload sessions
        sessions = UploadSession.objects.filter(owner=user).order_by('-created_at')
        
        # Paginate sessions
        paginator = Paginator(sessions, 10)
        page = request.GET.get('page', 1)
        sessions_page = paginator.get_page(page)
        
        # Madde Havuzu Statistics
        stats = {
            'total_pools': ItemPool.objects.filter(owner=user).count(),
            'total_items': ItemInstance.objects.filter(pool__owner=user).count(),
            'recent_activity': ItemAuditLog.objects.filter(user=user).order_by('-timestamp')[:10]
        }
        
        # Admin Global Stats
        if user.is_superuser or (hasattr(user, 'profile') and user.profile.role == 'ADMIN'):
            stats['global_pools'] = ItemPool.objects.count()
            stats['global_items'] = ItemInstance.objects.count()
            stats['global_activity'] = ItemAuditLog.objects.order_by('-timestamp')[:20]

        return render(request, 'grading/dashboard.html', {
            'sessions': sessions_page,
            'mh_stats': stats,
        })


class NewUploadView(LoginRequiredMixin, View):
    """File upload view."""
    
    def get(self, request):
        formats = FileFormatConfig.objects.filter(is_active=True)
        default_format = formats.filter(is_default=True).first() or formats.first()
        
        # Determine back_url
        referer = request.META.get('HTTP_REFERER', '')
        if 'yonetim' in referer:
            back_url = '/yonetim/yuklemeler/'
        else:
            back_url = '/panel/'

        return render(request, 'grading/upload_form.html', {
            'formats': formats,
            'default_format': default_format,
            'back_url': back_url,
        })

    def post(self, request):
        uploaded_file = request.FILES.get('file')
        if uploaded_file:
            uploaded_file.name = sanitize_filename(uploaded_file.name)
        format_id = request.POST.get('format')
        penalty_ratio = request.POST.get('penalty_ratio')
        points_per_question = request.POST.get('points_per_question', '1.0')
        # Sınav formu ve uygulama bağlantısı (opsiyonel)
        test_form_id = request.POST.get('test_form_id')
        exam_application_id = request.POST.get('exam_application_id')
        
        # Validation
        if not uploaded_file:
            messages.error(request, 'Lütfen bir dosya seçin.')
            return redirect('new_upload')
        
        # Check file extension
        if not uploaded_file.name.lower().endswith('.txt'):
            messages.error(request, 'Sadece .txt dosyaları kabul edilmektedir.')
            return redirect('new_upload')
        
        # Check file size (max 20MB)
        if uploaded_file.size > 20 * 1024 * 1024:
            messages.error(request, 'Dosya boyutu 20MB\'dan büyük olamaz.')
            return redirect('new_upload')
        
        # Get file format
        file_format = None
        if format_id:
            try:
                file_format = FileFormatConfig.objects.get(pk=format_id, is_active=True)
            except FileFormatConfig.DoesNotExist:
                pass
        
        if not file_format:
            file_format = FileFormatConfig.objects.filter(is_default=True, is_active=True).first()
        
        if not file_format:
            messages.error(
                request,
                'Dosya formatı bulunamadı. Lütfen admin panelinden bir format tanımlayın.'
            )
            return redirect('new_upload')

        # Test formu ve sınav uygulaması çözümle
        linked_test_form = None
        linked_exam_application = None
        if test_form_id:
            try:
                from itempool.models import TestForm
                linked_test_form = TestForm.objects.get(pk=test_form_id)
            except Exception:
                pass
        if exam_application_id:
            try:
                from itempool.models import ExamApplication
                linked_exam_application = ExamApplication.objects.get(pk=exam_application_id)
                if not linked_test_form and linked_exam_application.test_form:
                    linked_test_form = linked_exam_application.test_form
            except Exception:
                pass

        session = UploadSession.objects.create(
            owner=request.user,
            original_filename=uploaded_file.name,
            uploaded_file=uploaded_file,
            file_format=file_format,
            wrong_to_correct_ratio=int(penalty_ratio) if penalty_ratio and penalty_ratio.isdigit() else 0,
            points_per_question=float(points_per_question) if points_per_question else 1.0,
            processing_status=ProcessingStatus.QUEUED,
            test_form=linked_test_form,
            exam_application=linked_exam_application,
        )
        
        # Process the file
        parsing_service = ParsingService()
        success = parsing_service.process_upload(session)
        
        if success:
            messages.success(
                request,
                f'Dosya başarıyla işlendi! {session.student_count} öğrenci, '
                f'{session.question_count} soru.'
            )
            # Sınav formu bağlıysa otomatik madde analizi tetikle
            if linked_test_form and session.is_processed:
                try:
                    from itempool.services.analysis_service import ItemAnalysisService
                    item_mapping = {
                        fi.order - 1: fi.item_instance_id
                        for fi in linked_test_form.form_items.order_by('order')
                    }
                    count = ItemAnalysisService().process_session_results(
                        session, item_mapping, linked_test_form
                    )
                    if count > 0:
                        messages.info(request, f'{count} madde için analiz sonuçları otomatik kaydedildi.')
                except Exception as e:
                    messages.warning(request, f'Madde analizi kaydedilirken hata: {e}')
        else:
            messages.error(request, f'Dosya işlenirken hata oluştu: {session.error_summary}')

        # Sınav formu bağlıysa analiz paneline yönlendir
        if linked_test_form and success:
            return redirect('itempool:exam_grading_hub_session', pk=linked_test_form.pk, session_pk=session.pk)
        return redirect('upload_detail', pk=session.pk)


class UploadDetailView(LoginRequiredMixin, View):
    """View upload session details and results."""
    
    def get(self, request, pk):
        if request.user.is_staff:
            session = get_object_or_404(UploadSession, pk=pk)
        else:
            session = get_object_or_404(UploadSession, pk=pk, owner=request.user)
        
        # Get results with pagination
        results = session.results.all()
        paginator = Paginator(results, 25)
        page = request.GET.get('page', 1)
        results_page = paginator.get_page(page)
        
        # Get parsing errors
        errors = session.parsing_errors.all()
        
        # Determine back_url
        referer = request.META.get('HTTP_REFERER', '')
        if 'yonetim' in referer:
            back_url = '/yonetim/yuklemeler/'
        elif 'panel' in referer:
            back_url = '/panel/'
        else:
            # Default for staff is admin list, for others is personal list
            back_url = '/yonetim/yuklemeler/' if request.user.is_staff else '/panel/'
        
        return render(request, 'grading/upload_detail.html', {
            'session': session,
            'results': results_page,
            'errors': errors,
            'back_url': back_url,
        })


class DownloadExcelView(LoginRequiredMixin, View):
    """Download Excel results."""
    
    def get(self, request, pk):
        if request.user.is_staff:
            session = get_object_or_404(UploadSession, pk=pk)
        else:
            session = get_object_or_404(UploadSession, pk=pk, owner=request.user)
        
        if not session.is_processed:
            messages.error(request, 'Bu yükleme henüz işlenmedi.')
            return redirect('upload_detail', pk=pk)
        
        # Get results as dict list
        results = list(session.results.values(
            'student_no', 'student_name', 'booklet',
            'correct_count', 'wrong_count', 'blank_count',
            'invalid_count', 'score', 'detailed_results'
        ))
        
        # Calculate stats for the export
        stats_service = StatisticsService()
        stats = stats_service.calculate_session_stats(session)
        
        # Export to Excel
        export_service = ExcelExportService()
        
        penalty_ratio = session.wrong_to_correct_ratio or 0
        points_per_question = float(session.points_per_question or 1.0)
        
        # Use detail export if question count available
        if session.question_count:
            excel_file = export_service.export_with_details(
                results, 
                session.question_count,
                penalty_ratio=penalty_ratio,
                points_per_question=points_per_question,
                stats=stats
            )
        else:
            excel_file = export_service.export_results(
                results,
                penalty_ratio=penalty_ratio,
                points_per_question=points_per_question
            )
        
        # Create response
        filename = f"sonuclar_{session.pk}_{session.created_at.strftime('%Y%m%d_%H%M')}.xlsx"
        response = HttpResponse(
            excel_file.getvalue(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        return response

class UploadSessionDeleteView(LoginRequiredMixin, View):
    """Delete an upload session."""
    
    def post(self, request, pk):
        if request.user.is_staff:
            session = get_object_or_404(UploadSession, pk=pk)
        else:
            session = get_object_or_404(UploadSession, pk=pk, owner=request.user)
        filename = session.original_filename
        session.delete()
        
        messages.success(request, f'"{filename}" başlıklı sınav başarıyla silindi.')
        return redirect('dashboard')

class UpdatePenaltyView(LoginRequiredMixin, View):
    """Update penalty ratio and recalculate scores."""
    
    def post(self, request, pk):
        if request.user.is_staff:
            session = get_object_or_404(UploadSession, pk=pk)
        else:
            session = get_object_or_404(UploadSession, pk=pk, owner=request.user)
            
        penalty_ratio = request.POST.get('penalty_ratio')
        points_per_question = request.POST.get('points_per_question')
        
        session.wrong_to_correct_ratio = int(penalty_ratio) if penalty_ratio and penalty_ratio.isdigit() else 0
        if points_per_question:
            try:
                session.points_per_question = float(points_per_question)
            except ValueError:
                pass
        session.save()
        
        # Recalculate
        parsing_service = ParsingService()
        parsing_service.recalculate_scores(session)
        
        messages.success(request, 'Yanlış-doğru oranı güncellendi ve puanlar yeniden hesaplandı.')
        return redirect('upload_detail', pk=pk)

class UploadStatisticsView(LoginRequiredMixin, View):
    """View exam statistics, central tendency, and distribution."""
    
    def get(self, request, pk):
        if request.user.is_staff:
            session = get_object_or_404(UploadSession, pk=pk)
        else:
            session = get_object_or_404(UploadSession, pk=pk, owner=request.user)
            
        if not session.is_processed:
            messages.error(request, 'Bu sınavın istatistikleri henüz hazır değil.')
            return redirect('dashboard')
            
        stats_service = StatisticsService()
        stats = stats_service.calculate_session_stats(session)
        
        if not stats:
            messages.warning(request, 'İstatistik hesaplamak için yeterli veri bulunamadı.')
            return redirect('upload_detail', pk=pk)
            
        # Histogram data labels (str list for JS)
        histogram_labels = [str(i) for i in range(len(stats['histogram_bins']))]
        
        # Transform stats for template compatibility if needed
        for item in stats['item_analysis']:
            item['index'] = item['question_number']
            item['p_comment'] = item['difficulty']
            item['r_comment'] = item['discrimination']
            item['distractors'] = item['option_counts']
            item['is_problematic'] = item['r'] < 0.20 or item['p'] < 0.10 or item['p'] > 0.95

        # Determine back_url (usually back to detail)
        back_url = f'/yuklemeler/{pk}/'

        context = {
            'session': session,
            'stats': stats,
            'mean': round(stats['mean'], 2),
            'median': round(stats['median'], 2),
            'std_dev': round(stats['std_dev'], 2),
            'histogram_data': stats['histogram_bins'],
            'histogram_labels': histogram_labels,
            'dist_interpretation': stats['dist_interpretation'],
            'group_structure': stats['group_structure'],
            'interpretation_type': stats['interpretation_type'],
            'student_count': stats['student_count'],
            'item_analysis': stats['item_analysis'],
            'back_url': back_url,
        }
        
        return render(request, 'grading/upload_stats.html', context)


class KR20StatisticsView(LoginRequiredMixin, View):
    """View KR-20 reliability analysis for an exam."""
    
    def get(self, request, pk):
        if request.user.is_staff:
            session = get_object_or_404(UploadSession, pk=pk)
        else:
            session = get_object_or_404(UploadSession, pk=pk, owner=request.user)
            
        if not session.is_processed:
            messages.error(request, 'Bu sınavın KR-20 analizi henüz hazır değil.')
            return redirect('dashboard')
            
        stats_service = StatisticsService()
        kr20_stats = stats_service.calculate_kr20(session)
        
        if not kr20_stats:
            messages.warning(request, 'KR-20 hesaplamak için yeterli veri bulunamadı (En az 2 soru gerekli).')
            return redirect('upload_stats', pk=pk)
        
        # Determine back_url
        back_url = f'/yuklemeler/{pk}/'

        context = {
            'session': session,
            'kr20': kr20_stats['kr20'],
            'k': kr20_stats['k'],
            'n': kr20_stats['n'],
            'sum_pq': kr20_stats['sum_pq'],
            'variance': kr20_stats['variance'],
            'mean_score': kr20_stats['mean_score'],
            'interpretation': kr20_stats['interpretation'],
            'interpretation_type': kr20_stats['interpretation_type'],
            'item_stats': kr20_stats['item_stats'],
            'back_url': back_url,
        }
        
        return render(request, 'grading/kr20_stats.html', context)


class AlphaStatisticsView(LoginRequiredMixin, View):
    """View Cronbach's Alpha reliability analysis for an exam."""
    
    def get(self, request, pk):
        if request.user.is_staff:
            session = get_object_or_404(UploadSession, pk=pk)
        else:
            session = get_object_or_404(UploadSession, pk=pk, owner=request.user)
            
        if not session.is_processed:
            messages.error(request, 'Bu sınavın Cronbach Alpha analizi henüz hazır değil.')
            return redirect('dashboard')
            
        stats_service = StatisticsService()
        alpha_stats = stats_service.calculate_cronbach_alpha(session)
        
        if not alpha_stats:
            messages.warning(request, 'Cronbach Alpha hesaplamak için yeterli veri bulunamadı (En az 2 soru gerekli).')
            return redirect('upload_stats', pk=pk)
        
        # Determine back_url
        back_url = f'/yuklemeler/{pk}/'

        context = {
            'session': session,
            'alpha': alpha_stats['alpha'],
            'k': alpha_stats['k'],
            'n': alpha_stats['n'],
            'sum_item_variance': alpha_stats['sum_item_variance'],
            'total_variance': alpha_stats['total_variance'],
            'mean_score': alpha_stats['mean_score'],
            'interpretation': alpha_stats['interpretation'],
            'interpretation_type': alpha_stats['interpretation_type'],
            'item_stats': alpha_stats['item_stats'],
            'back_url': back_url,
        }
        
        return render(request, 'grading/alpha_stats.html', context)


