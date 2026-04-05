import time
from django.core.management.base import BaseCommand
from itempool.models import Item, ItemEmbedding
from itempool.services.llm_client import get_llm_client

class Command(BaseCommand):
    help = 'Tüm maddeleri (veya eksik olanları) vektörize eder.'

    def add_arguments(self, parser):
        parser.add_argument('--force', action='store_true', help='Tümünü yeniden hesapla')

    def handle(self, *args, **options):
        force = options['force']
        
        items_qs = Item.objects.all()
        if not force:
            items_qs = items_qs.filter(embedding__isnull=True)
            
        total = items_qs.count()
        if total == 0:
            self.stdout.write(self.style.SUCCESS("Vektörize edilecek madde bulunamadı."))
            return

        self.stdout.write(f"{total} adet madde vektörize ediliyor...")
        
        client = get_llm_client()
        count = 0
        
        for item in items_qs:
            text = self.get_item_text_for_embedding(item)
            vector = client.get_embedding(text)
            
            if vector:
                ItemEmbedding.objects.update_or_create(
                    item=item,
                    defaults={'vector': vector}
                )
                count += 1
                if count % 10 == 0:
                    self.stdout.write(f"İlerleme: {count}/{total}")
                # Rate limit önlemi
                time.sleep(0.5)
            else:
                self.stderr.write(self.style.ERROR(f"Hata: Madde #{item.id} için embedding alınamadı."))

        self.stdout.write(self.style.SUCCESS(f"Tamamlandı: {count} madde vektörize edildi."))

    def get_item_text_for_embedding(self, item):
        text = f"Soru: {item.stem}\n"
        if item.item_type in [Item.ItemType.MULTIPLE_CHOICE, Item.ItemType.TRUE_FALSE]:
            choices = "\n".join([f"{c.label}: {c.text}" for c in item.choices.all()])
            text += f"Seçenekler:\n{choices}"
        elif item.item_type == Item.ItemType.SHORT_ANSWER:
            text += f"Beklenen Cevap: {item.expected_answer or ''}"
        return text
