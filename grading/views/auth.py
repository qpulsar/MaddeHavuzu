"""
Authentication views: login, register, logout.
"""
from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.models import User
from django.contrib import messages
from django.views import View

from grading.models import UserProfile, UserStatus


class LandingView(View):
    """Landing page with login/register options."""
    
    def get(self, request):
        if request.user.is_authenticated:
            return redirect('dashboard')
        return render(request, 'grading/landing.html')


class RegisterView(View):
    """User registration view."""
    
    def get(self, request):
        if request.user.is_authenticated:
            return redirect('dashboard')
        return render(request, 'registration/register.html')
    
    def post(self, request):
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '')
        password_confirm = request.POST.get('password_confirm', '')
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        
        # Validation
        errors = []
        
        if not username:
            errors.append('Kullanıcı adı gereklidir.')
        elif User.objects.filter(username=username).exists():
            errors.append('Bu kullanıcı adı zaten kullanılıyor.')
        
        if not email:
            errors.append('E-posta adresi gereklidir.')
        elif User.objects.filter(email=email).exists():
            errors.append('Bu e-posta adresi zaten kayıtlı.')
        
        if not password:
            errors.append('Şifre gereklidir.')
        elif len(password) < 8:
            errors.append('Şifre en az 8 karakter olmalıdır.')
        elif password != password_confirm:
            errors.append('Şifreler eşleşmiyor.')
        
        if errors:
            for error in errors:
                messages.error(request, error)
            return render(request, 'registration/register.html', {
                'username': username,
                'email': email,
                'first_name': first_name,
                'last_name': last_name,
            })
        
        # Create user
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
        )
        
        # Create profile with PENDING status
        UserProfile.objects.create(user=user, status=UserStatus.PENDING)
        
        messages.success(
            request,
            'Kayıt başarılı! Hesabınız admin onayı bekliyor. '
            'Onaylandıktan sonra giriş yapabileceksiniz.'
        )
        return redirect('login')


class CustomLoginView(View):
    """Custom login view with status checking."""
    
    def get(self, request):
        if request.user.is_authenticated:
            return redirect('dashboard')
        return render(request, 'registration/login.html')
    
    def post(self, request):
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        
        if not username or not password:
            messages.error(request, 'Kullanıcı adı ve şifre gereklidir.')
            return render(request, 'registration/login.html', {'username': username})
        
        # Check if user exists
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            messages.error(request, 'Kullanıcı adı veya şifre hatalı.')
            return render(request, 'registration/login.html', {'username': username})
        
        # Check password
        if not user.check_password(password):
            messages.error(request, 'Kullanıcı adı veya şifre hatalı.')
            return render(request, 'registration/login.html', {'username': username})
        
        # Superuser can always login
        if user.is_superuser:
            login(request, user, backend='grading.backends.ApprovedUserBackend')
            return redirect('dashboard')
        
        # Check profile status
        if not hasattr(user, 'profile'):
            messages.error(request, 'Hesap durumu geçersiz. Lütfen yönetici ile iletişime geçin.')
            return render(request, 'registration/login.html', {'username': username})
        
        profile = user.profile
        status_messages = {
            UserStatus.PENDING: 'Hesabınız henüz onaylanmadı. Lütfen admin onayını bekleyin.',
            UserStatus.REJECTED: 'Hesabınız reddedildi. Daha fazla bilgi için yönetici ile iletişime geçin.',
            UserStatus.SUSPENDED: 'Hesabınız askıya alındı. Daha fazla bilgi için yönetici ile iletişime geçin.',
        }
        
        if profile.status != UserStatus.APPROVED:
            messages.warning(request, status_messages.get(profile.status, 'Giriş yapılamıyor.'))
            return render(request, 'registration/login.html', {'username': username})
        
        # All checks passed, login
        login(request, user, backend='grading.backends.ApprovedUserBackend')
        messages.success(request, f'Hoş geldiniz, {user.first_name or user.username}!')
        
        # Redirect to next or dashboard
        next_url = request.GET.get('next') or request.POST.get('next')
        return redirect(next_url if next_url else 'dashboard')


class CustomLogoutView(View):
    """Logout view."""
    
    def get(self, request):
        logout(request)
        messages.info(request, 'Başarıyla çıkış yaptınız.')
        return redirect('landing')
    
    def post(self, request):
        return self.get(request)
