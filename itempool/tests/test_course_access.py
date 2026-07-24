import pytest
from django.contrib.auth.models import User
from django.urls import reverse
from itempool.models import Course
from grading.models import UserProfile, UserStatus, UserRole


@pytest.mark.django_db
def test_course_detail_admin_access(client):
    # 1. Hocayı ve hocaya ait dersi oluştur
    instructor = User.objects.create_user('hoca1', 'hoca1@example.com', 'pass1234')
    course = Course.objects.create(name='Matematik I', code='MAT101', created_by=instructor)

    # 2. Admin kullanıcısını oluştur
    admin_user = User.objects.create_superuser('admin', 'admin@example.com', 'pass1234')
    client.force_login(admin_user)

    # 3. Admin hocanın ders detay sayfasına erişebilmeli (Daha önce 404 veriyordu)
    url = reverse('itempool:course_detail', kwargs={'pk': course.pk})
    response = client.get(url)
    assert response.status_code == 200
    assert 'Matematik I' in response.content.decode('utf-8')


@pytest.mark.django_db
def test_course_detail_owner_and_other_instructor_access(client):
    hoca1 = User.objects.create_user('hoca1', 'hoca1@example.com', 'pass1234')
    hoca2 = User.objects.create_user('hoca2', 'hoca2@example.com', 'pass1234')
    course = Course.objects.create(name='Fizik I', code='FIZ101', created_by=hoca1)

    # Sahibi (hoca1) erişebilmeli
    client.force_login(hoca1)
    url = reverse('itempool:course_detail', kwargs={'pk': course.pk})
    res1 = client.get(url)
    assert res1.status_code == 200

    # Başka hoca (hoca2) erişmeye çalıştığında 404 almalı
    client.force_login(hoca2)
    res2 = client.get(url)
    assert res2.status_code == 404
