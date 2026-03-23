import json
from django.shortcuts import render, redirect
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.http import JsonResponse
from django.views import View
from django.views.decorators.http import require_POST
from django.utils.decorators import method_decorator

VALID_THEMES   = {'light', 'dark', 'system'}
VALID_PALETTES = {'ocean', 'forest', 'sunset', 'amethyst', 'midnight', 'rose'}


class ProfileView(LoginRequiredMixin, View):
    """View to display and update user profile + appearance settings."""

    def get(self, request):
        return render(request, 'grading/profile.html')

    def post(self, request):
        user    = request.user
        profile = user.profile

        first_name = request.POST.get('first_name', '').strip()
        last_name  = request.POST.get('last_name', '').strip()
        email      = request.POST.get('email', '').strip()

        if not email:
            messages.error(request, 'E-posta adresi boş bırakılamaz.')
            return render(request, 'grading/profile.html')

        user.first_name = first_name
        user.last_name  = last_name
        user.email      = email
        user.save()

        # Görünüm tercihleri
        new_theme   = request.POST.get('theme', 'light')
        new_palette = request.POST.get('color_palette', 'ocean')
        if new_theme in VALID_THEMES:
            profile.theme = new_theme
        if new_palette in VALID_PALETTES:
            profile.color_palette = new_palette
        profile.save(update_fields=['theme', 'color_palette'])

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
            update_session_auth_hash(request, user)
            messages.success(request, 'Şifreniz başarıyla değiştirildi.')
            return redirect('profile')
        else:
            for error in form.errors.values():
                messages.error(request, error)
            return render(request, 'grading/change_password.html', {'form': form})


@method_decorator(require_POST, name='dispatch')
class SetThemeView(LoginRequiredMixin, View):
    """
    AJAX endpoint: hızlı tema değiştirme (topbar toggle).
    Body: {"theme": "light"|"dark"|"system"}
          {"color_palette": "ocean"|...}
    """
    def post(self, request):
        try:
            data    = json.loads(request.body)
            profile = request.user.profile
            changed = []
            if 'theme' in data and data['theme'] in VALID_THEMES:
                profile.theme = data['theme']
                changed.append('theme')
            if 'color_palette' in data and data['color_palette'] in VALID_PALETTES:
                profile.color_palette = data['color_palette']
                changed.append('color_palette')
            if changed:
                profile.save(update_fields=changed)
        except Exception:
            pass
        return JsonResponse({'ok': True})
