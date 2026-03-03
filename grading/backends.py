from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.models import User


class ApprovedUserBackend(ModelBackend):
    """
    Custom authentication backend that only allows approved users to log in.
    """
    
    def authenticate(self, request, username=None, password=None, **kwargs):
        """
        Authenticate user but check approval status.
        Returns None if user is not approved, preventing login.
        """
        user = super().authenticate(request, username=username, password=password, **kwargs)
        if user is None:
            return None
        
        # Check if user is approved (superusers are always allowed)
        if user.is_superuser or (hasattr(user, 'profile') and user.profile.can_login):
            return user
            
        return None
    
    def get_user(self, user_id):
        """Get user by ID."""
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None
