import random
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.contrib.auth.models import User
from itempool.models import ItemPool, Item, ItemInstance, ItemChoice, TestForm, FormItem, Course, ExamApplication

class Command(BaseCommand):
    help = 'Eğitim Psikolojisi dışındaki havuzları ve test verilerini siler. Eğitim Sosyolojisi ve Öğretim Teknolojisi havuzlarını oluşturup test verileri ekler.'

    def handle(self, *args, **kwargs):
        self.stdout.write("Test verileri temizleniyor...")
        
        # Admin kullanıcısını bul
        try:
            admin_user = User.objects.filter(is_superuser=True).first()
            if not admin_user:
                admin_user = User.objects.first()
            if not admin_user:
                # Eger hic kullanici yoksa gecici olarak bir tane olustur
                admin_user = User.objects.create_superuser('admin', 'admin@example.com', 'admin')
        except Exception:
            self.stdout.write(self.style.ERROR("Kullanıcı bulunamadı/oluşturulamadı."))
            return

        # 1. Eğitim Psikolojisi olan havuzları bul
        preserved_pools = ItemPool.objects.filter(name__icontains="eğitim psikolojisi")
        preserved_pool_ids = preserved_pools.values_list('id', flat=True)
        
        # 2. Silinecek verileri temizle
        # Korunan havuzlarla bağlantılı olmayan Course, TestForm, ExamApplication'ları sil
        # Ancak basitlik adına bu scriptte Eğitim Psikolojisine ait Course/TestFormları da koruma kapsamındaysa filtrelemeliydik.
        # Eğitsel veritabanında test amaçlı hepsi silinsin deniyor, sadece "havuzlar" (Eğitim Psikolojisi olan) kalsın isteniyor.
        # Bu yüzden Course, TestForm, ExamApplication'ları güvenle sıfırlayabiliriz (veya Eğitim Psikolojisi olan formları koruruz).
        
        preserved_form_ids = TestForm.objects.filter(pools__in=preserved_pool_ids).values_list('id', flat=True)
        preserved_course_ids = Course.objects.filter(pools__in=preserved_pool_ids).values_list('id', flat=True)

        ExamApplication.objects.exclude(test_form__id__in=preserved_form_ids).delete()
        TestForm.objects.exclude(id__in=preserved_form_ids).delete()
        Course.objects.exclude(id__in=preserved_course_ids).delete()
        
        # Korunan Item'ları (madde) bul:
        preserved_item_ids = ItemInstance.objects.filter(pool__in=preserved_pool_ids).values_list('item_id', flat=True)
        
        # Korunmayan Instance ve Pool'ları sil
        ItemInstance.objects.exclude(pool__in=preserved_pool_ids).delete()
        ItemPool.objects.exclude(id__in=preserved_pool_ids).delete()
        
        # Korunmayan Item'ları sil
        Item.objects.exclude(id__in=preserved_item_ids).delete()
        
        self.stdout.write(self.style.SUCCESS("Eski test verileri temizlendi. 'Eğitim Psikolojisi' havuzu ve soruları korundu."))

        # 3. Yeni Havuzları oluştur
        new_pools_data = ["Eğitim Sosyolojisi", "Öğretim Teknolojisi"]
        
        for pool_name in new_pools_data:
            pool = ItemPool.objects.create(
                name=pool_name,
                description=f"{pool_name} için otomatik oluşturulmuş test havuzu.",
                level="Lisans 1",
                owner=admin_user,
                status=ItemPool.Status.ACTIVE
            )
            
            # Course oluştur (Uygulama için)
            course = Course.objects.create(
                name=pool_name + " Dersi",
                code="TEST101",
                semester="2026-Güz",
                created_by=admin_user
            )
            course.pools.add(pool)
            
            self.stdout.write(f"{pool_name} havuzu oluşturuluyor...")
            
            # Soru tiplerine göre 10'ar soru oluştur
            item_types = [
                Item.ItemType.MULTIPLE_CHOICE,
                Item.ItemType.TRUE_FALSE,
                Item.ItemType.MATCHING,
                Item.ItemType.OPEN_ENDED,
            ]
            
            created_instances = []
            
            for itype in item_types:
                for i in range(10):
                    item = Item.objects.create(
                        stem=f"{pool_name} - {itype.label} Örnek Soru {i+1}?\nAşağıdakilerden hangisi doğrudur?",
                        item_type=itype,
                        difficulty_intended=random.choice(Item.Difficulty.choices)[0],
                        author=admin_user,
                        status=Item.Status.ACTIVE
                    )
                    
                    if itype == Item.ItemType.MULTIPLE_CHOICE:
                        item.max_choices = 5
                        item.save()
                        choices = ["A", "B", "C", "D", "E"]
                        correct_idx = random.randint(0, 4)
                        for idx, label in enumerate(choices):
                            ItemChoice.objects.create(
                                item=item,
                                label=label,
                                text=f"Seçenek {label} metni.",
                                is_correct=(idx == correct_idx),
                                order=idx
                            )
                    elif itype == Item.ItemType.TRUE_FALSE:
                        item.max_choices = 2
                        item.save()
                        ItemChoice.objects.create(
                            item=item, label="D", text="Doğru", is_correct=True, order=0
                        )
                        ItemChoice.objects.create(
                            item=item, label="Y", text="Yanlış", is_correct=False, order=1
                        )
                    elif itype == Item.ItemType.OPEN_ENDED:
                        item.scoring_rubric = "Puanlama kriterleri:\n1. Açıklık (5p)\n2. Doğruluk (5p)"
                        item.save()
                    elif itype == Item.ItemType.MATCHING:
                        item.expected_answer = "Eşleştirme:\n1-A\n2-B\n3-C"
                        item.save()
                        
                    instance = ItemInstance.objects.create(
                        pool=pool,
                        item=item,
                        added_by=admin_user
                    )
                    created_instances.append(instance)

            # 4. Sınav (TestForm) oluştur: 3 Sınav (Vize, Final, Bütünleme)
            exam_names = ["Vize Sınavı", "Final Sınavı", "Bütünleme Sınavı"]
            
            for exam_name in exam_names:
                form = TestForm.objects.create(
                    name=f"{pool_name} - {exam_name}",
                    description=f"{pool_name} dersinin {exam_name}.",
                    course=course,
                    status=TestForm.Status.ACTIVE,
                    created_by=admin_user
                )
                form.pools.add(pool)
                
                # Rastgele 20 soru seç (TestForm için)
                selected_instances = random.sample(created_instances, min(20, len(created_instances)))
                for order, instance in enumerate(selected_instances, start=1):
                    FormItem.objects.create(
                        form=form,
                        item_instance=instance,
                        order=order,
                        points=5.0
                    )
                
                # 5. ExamApplication (Sınav Uygulaması) oluştur
                app_date = timezone.now().date() + timedelta(days=random.randint(1, 30))
                ExamApplication.objects.create(
                    test_form=form,
                    course=course,
                    applied_at=app_date,
                    notes=f"{exam_name} test uygulaması",
                    created_by=admin_user
                )
                
            self.stdout.write(self.style.SUCCESS(f"{pool.name} havuzu ve sınavları oluşturuldu."))
            
        self.stdout.write(self.style.SUCCESS("Tüm işlemler başarıyla tamamlandı."))
