from django.db import models
from django.contrib.auth.models import User


class UserStatus(models.TextChoices):
    """User approval status choices."""
    PENDING = 'PENDING', 'Onay Bekliyor'
    APPROVED = 'APPROVED', 'Onaylı'
    REJECTED = 'REJECTED', 'Reddedildi'
    SUSPENDED = 'SUSPENDED', 'Askıya Alındı'


class UserProfile(models.Model):
    """
    Extended user profile for approval workflow.
    Each user must be approved by an admin before they can log in.
    """
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='profile',
        verbose_name='Kullanıcı'
    )
    status = models.CharField(
        max_length=20,
        choices=UserStatus.choices,
        default=UserStatus.PENDING,
        verbose_name='Durum'
    )
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_users',
        verbose_name='Onaylayan'
    )
    approved_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Onay Tarihi'
    )
    note = models.TextField(
        blank=True,
        verbose_name='Not',
        help_text='Admin tarafından eklenen not'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Kayıt Tarihi'
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='Güncelleme Tarihi'
    )

    class Meta:
        verbose_name = 'Kullanıcı Profili'
        verbose_name_plural = 'Kullanıcı Profilleri'

    def __str__(self):
        return f"{self.user.username} - {self.get_status_display()}"

    @property
    def is_approved(self):
        """Check if user is approved."""
        return self.status == UserStatus.APPROVED

    @property
    def can_login(self):
        """Check if user can log in."""
        return self.status == UserStatus.APPROVED
