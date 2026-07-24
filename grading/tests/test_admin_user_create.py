import pytest
from django.contrib.auth.models import User
from django.urls import reverse
from grading.models import UserProfile, UserStatus, UserRole


@pytest.mark.django_db
def test_admin_user_create_success(client):
    admin_user = User.objects.create_superuser('adminuser', 'admin@example.com', 'pass1234')
    client.force_login(admin_user)

    url = reverse('admin_user_create')
    post_data = {
        'username': 'yeni.hoca',
        'first_name': 'Ayşe',
        'last_name': 'Demir',
        'email': 'ayse@universite.edu.tr',
        'password': 'password123',
        'role': 'INSTRUCTOR',
    }

    response = client.post(url, post_data)
    assert response.status_code == 302

    created_user = User.objects.get(username='yeni.hoca')
    assert created_user.email == 'ayse@universite.edu.tr'
    assert created_user.first_name == 'Ayşe'

    profile = UserProfile.objects.get(user=created_user)
    assert profile.status == UserStatus.APPROVED
    assert profile.role == UserRole.INSTRUCTOR
    assert profile.approved_by == admin_user


@pytest.mark.django_db
def test_admin_user_create_duplicate_username(client):
    admin_user = User.objects.create_superuser('adminuser', 'admin@example.com', 'pass1234')
    User.objects.create_user('mevcut.user', 'mevcut@example.com', 'pass1234')
    client.force_login(admin_user)

    url = reverse('admin_user_create')
    post_data = {
        'username': 'mevcut.user',
        'email': 'farkli@universite.edu.tr',
        'password': 'password123',
    }

    response = client.post(url, post_data)
    assert response.status_code == 302
    assert User.objects.filter(email='farkli@universite.edu.tr').exists() is False
