
from django.shortcuts import render, get_object_or_404, redirect
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from grading.models import UploadSession
from grading.services.analysis import CheatingAnalysisService

class CheatingAnalysisView(LoginRequiredMixin, View):
    """View for performing and displaying cheating analysis."""
    
    def get(self, request, pk):
        if request.user.is_staff:
            session = get_object_or_404(UploadSession, pk=pk)
        else:
            session = get_object_or_404(UploadSession, pk=pk, owner=request.user)
            
        if not session.is_processed:
            messages.error(request, 'Bu sınav henüz işlenmediği için kopya analizi yapılamaz.')
            return redirect('dashboard')
            
        # Default analysis params or from GET
        try:
            exclude_top = float(request.GET.get('exclude_top', 0))
            same_wrong_weight = float(request.GET.get('same_wrong_weight', 1.5))
            disc_weight = float(request.GET.get('disc_weight', 1.0))
        except ValueError:
            exclude_top = 0
            same_wrong_weight = 1.5
            disc_weight = 1.0
            
        service = CheatingAnalysisService(session)
        analysis_result = service.analyze(
            exclude_top_percent=exclude_top,
            same_wrong_weight=same_wrong_weight,
            discrimination_weight_factor=disc_weight
        )
        
        if 'error' in analysis_result:
            messages.warning(request, analysis_result['error'])
            return redirect('upload_detail', pk=pk)

        # Back url
        back_url = f'/yuklemeler/{pk}/'
        
        context = {
            'session': session,
            'risky_pairs': analysis_result['risky_pairs'],
            'stats': analysis_result['stats'],
            'params': analysis_result['parameters'],
            'back_url': back_url
        }
        
        return render(request, 'grading/cheating_analysis.html', context)
