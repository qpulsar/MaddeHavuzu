from django.shortcuts import render, redirect
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.views import View

class ProfileView(LoginRequiredMixin, View):
    """View to display and update user profile information."""
    
    def get(self, request):
        return render(request, 'grading/profile.html')
    
    def post(self, request):
        user = request.user
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        email = request.POST.get('email', '').strip()
        
        # Simple validation
        if not email:
            messages.error(request, 'E-posta adresi boş bırakılamaz.')
            return render(request, 'grading/profile.html')
            
        user.first_name = first_name
        user.last_name = last_name
        user.email = email
        user.save()
        
        messages.success(request, 'Profil bilgileriniz başarıyla güncellendi.')
        return redirect('profile')

class ChangePasswordView(LoginRequiredMixin, View):
    """View to handle password change."""
    
    def get(self, request):
        form = PasswordChangeForm(request.user)
        return render(request, 'grading/change_password.html', {'form': form})
    
    def post(self, request):
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            # Authentication hash'ini güncelle ki kullanıcı oturumu kapanmasın
            update_session_auth_hash(request, user)
            messages.success(request, 'Şifreniz başarıyla değiştirildi.')
            return redirect('profile')
        else:
            for error in form.errors.values():
                messages.error(request, error)
            return render(request, 'grading/change_password.html', {'form': form})
