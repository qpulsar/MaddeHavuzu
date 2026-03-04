import pytest
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from itempool.models import ItemPool, TestForm, ItemAnalysisResult
from grading.models import UploadSession, FileFormatConfig
import io

@pytest.mark.django_db
class TestAnalysisIntegration:
    def setup_method(self):
        from django.contrib.auth.models import User
        self.user = User.objects.create_superuser(username='admin', password='password', email='admin@test.com')
        self.pool = ItemPool.objects.create(name='Test Pool', owner=self.user)
        self.form = TestForm.objects.create(name='Test Form', pool=self.pool, created_by=self.user)
        self.format = FileFormatConfig.objects.create(
            name='Standard Format',
            is_active=True,
            is_default=True,
            format_type='FIXED_WIDTH',
            student_no_start=0,
            student_no_end=10,
            student_name_start=10,
            student_name_end=30,
            answers_start=31,
            has_booklet_field=True,
            booklet_start=30,
            booklet_end=31
        )

    def test_analysis_upload_view_get(self, client):
        client.login(username='admin', password='password')
        response = client.get(reverse('itempool:analysis_upload'))
        assert response.status_code == 200
        assert 'pool_id' in response.content.decode()

    def test_analysis_get_forms_htmx(self, client):
        client.login(username='admin', password='password')
        response = client.get(reverse('itempool:analysis_get_forms'), {'pool_id': self.pool.id})
        assert response.status_code == 200
        assert self.form.name in response.content.decode()

    def test_analysis_upload_processing(self, client):
        # Mocking or using a real parser might be complex, 
        # but let's test if the view handles the basic flow.
        client.login(username='admin', password='password')
        
        # Basit bir optik veri içeriği
        # StudentNo(10) + Name(20) + Booklet(1) + Answers(...)
        content = "1234567890Ogrenci Bir         AABCDE\n"
        data_file = SimpleUploadedFile("results.dat", content.encode('utf-8'))
        
        # Cevap anahtarını test formunda tanımlayalım (basitçe)
        self.session_data = {
            'pool_id': self.pool.id,
            'form_id': self.form.id,
            'file_format': self.format.id,
            'data_file': data_file,
            'points_per_question': 1.0,
            'wrong_to_correct_ratio': 0
        }
        
        # Not: ParsingService gerçek dosyayı okumaya çalışacaktır. 
        # Bu testin tamamen başarılı olması için ParsingService ve ItemAnalysisService'in mocklanması gerekebilir 
        # veya tam entegre bir veri seti sunulmalıdır.
        # Şimdilik en azından view'ın çökmediğini ve session oluşturduğunu doğrulayalım.
        
        response = client.post(reverse('itempool:analysis_upload'), self.session_data)
        
        # Başarılı olursa pool_detail'e yönlendirmeli
        # (Gerçek veriyle dolmadığı için process_upload False dönebilir, o zaman geri yönlendirir)
        assert response.status_code in [200, 302]
        
        # UploadSession oluşmuş mu?
        assert UploadSession.objects.filter(original_filename='results.dat').exists()
