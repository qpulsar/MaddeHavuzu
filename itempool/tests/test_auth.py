import pytest
from django.urls import reverse
from django.contrib.auth.models import User
from itempool.models import ItemPool, PoolPermission
from grading.models.user_profile import UserProfile, UserRole

@pytest.mark.django_db
class TestPoolAuthorization:
    def setup_method(self):
        # Users
        self.admin = User.objects.create_superuser(username='admin', password='password')
        UserProfile.objects.create(user=self.admin, role=UserRole.ADMIN, status='APPROVED')
        
        self.owner = User.objects.create_user(username='owner', password='password')
        UserProfile.objects.create(user=self.owner, role=UserRole.INSTRUCTOR, status='APPROVED')
        
        self.viewer = User.objects.create_user(username='viewer', password='password')
        UserProfile.objects.create(user=self.viewer, role=UserRole.INSTRUCTOR, status='APPROVED')
        
        self.stranger = User.objects.create_user(username='stranger', password='password')
        UserProfile.objects.create(user=self.stranger, role=UserRole.INSTRUCTOR, status='APPROVED')

        # Pool
        self.pool = ItemPool.objects.create(
            name='Protected Pool',
            course='Test Course',
            owner=self.owner
        )
        
        # Permissions
        PoolPermission.objects.create(pool=self.pool, user=self.viewer, level='VIEWER')

    def test_pool_list_filtering(self, client):
        # Admin sees all
        client.login(username='admin', password='password')
        response = client.get(reverse('itempool:pool_list'))
        assert self.pool.name in response.content.decode()
        
        # Owner sees their pool
        client.login(username='owner', password='password')
        response = client.get(reverse('itempool:pool_list'))
        assert self.pool.name in response.content.decode()
        
        # Viewer sees pool they have permission for
        client.login(username='viewer', password='password')
        response = client.get(reverse('itempool:pool_list'))
        assert self.pool.name in response.content.decode()
        
        # Stranger sees nothing
        client.login(username='stranger', password='password')
        response = client.get(reverse('itempool:pool_list'))
        assert self.pool.name not in response.content.decode()

    def test_pool_detail_access(self, client):
        url = reverse('itempool:pool_detail', kwargs={'pk': self.pool.id})
        
        # Admin can access
        client.login(username='admin', password='password')
        response = client.get(url)
        assert response.status_code == 200
        
        # Owner can access
        client.login(username='owner', password='password')
        response = client.get(url)
        assert response.status_code == 200
        
        # Viewer can access
        client.login(username='viewer', password='password')
        response = client.get(url)
        assert response.status_code == 200
        
        # Stranger is denied (403 via UserPassesTestMixin)
        client.login(username='stranger', password='password')
        response = client.get(url)
        assert response.status_code == 403

    def test_pool_permission_levels(self, client):
        # This can be expanded to test EDITOR/MANAGER levels once more views use the mixin
        pass
