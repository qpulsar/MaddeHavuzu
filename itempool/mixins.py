from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.shortcuts import get_object_or_404
from .models import ItemPool, PoolPermission

class PoolAccessMixin(LoginRequiredMixin, UserPassesTestMixin):
    """
    Havuz bazlı yetki kontrolü yapan mixin.
    """
    pool_permission_required = 'VIEWER' # VIEWER, EDITOR, MANAGER

    def get_pool(self):
        pool_id = self.kwargs.get('pool_id') or self.kwargs.get('pk')
        if not pool_id:
            # Bazı view'lar (PoolListView gibi) havuz ID'si almaz
            return None
        return get_object_or_404(ItemPool, id=pool_id)

    def test_func(self):
        user = self.request.user
        if not user.is_authenticated:
            return False
            
        # Admin her şeyi yapabilir
        if user.is_superuser or (hasattr(user, 'profile') and user.profile.role == 'ADMIN'):
            return True
            
        pool = self.get_pool()
        if not pool:
            return True # Havuz listesi gibi genel görünümler için
            
        # Havuz sahibi her şeyi yapabilir
        if pool.owner == user:
            return True
            
        # Spesifik yetki kontrolü
        try:
            perm = PoolPermission.objects.get(pool=pool, user=user)
            
            levels = {
                'VIEWER': 1,
                'EDITOR': 2,
                'MANAGER': 3
            }
            
            required_level = levels.get(self.pool_permission_required, 1)
            user_level = levels.get(perm.level, 1)
            
            return user_level >= required_level
        except PoolPermission.DoesNotExist:
            return False
