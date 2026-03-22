"""
Eğitim Psikolojisi dersi için örnek veri oluşturur:
  - 2 madde havuzu (Öğrenme Teorileri, Gelişim ve Motivasyon)
  - Her havuzda 4 öğrenme çıktısı
  - Her soru türünden (MCQ, TF, SHORT_ANSWER, OPEN) en az 5 soru
  - 3 sınav formu: Vize, Final, Bütünleme
  - 3 farklı şablona göre PDF üretimi → sample_pdfs/
"""

import os
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User


class Command(BaseCommand):
    help = "Eğitim Psikolojisi örnek verisini oluşturur"

    def handle(self, *args, **options):
        from itempool.models import (
            ItemPool, LearningOutcome, Item, ItemChoice,
            ItemInstance, TestForm, FormItem, ExamTemplate,
        )
        from itempool.management.commands.seed_exam_templates import Command as SeedTemplates
        from itempool.services.exam_pdf import generate_exam_pdf

        # ── Kullanıcı ────────────────────────────────────────────────────────
        user = User.objects.filter(is_superuser=True).first()
        if not user:
            user = User.objects.create_superuser("admin", "admin@example.com", "admin1234")
            self.stdout.write("Superuser oluşturuldu: admin / admin1234")

        # ── Şablonlar ────────────────────────────────────────────────────────
        if ExamTemplate.objects.count() == 0:
            SeedTemplates().handle()
            self.stdout.write("Sınav şablonları oluşturuldu.")
        templates = list(ExamTemplate.objects.all()[:3])

        # ── Havuz 1: Öğrenme Teorileri ───────────────────────────────────────
        pool1, _ = ItemPool.objects.get_or_create(
            name="Eğitim Psikolojisi — Öğrenme Teorileri",
            defaults=dict(
                course="Eğitim Psikolojisi",
                semester="2024-Güz",
                level="Lisans 1",
                owner=user,
                status=ItemPool.Status.ACTIVE,
            ),
        )

        ot1 = self._outcome(pool1, "ÖT-1", "Davranışçı öğrenme teorilerini açıklar", "COMPREHENSION", 1)
        ot2 = self._outcome(pool1, "ÖT-2", "Bilişsel öğrenme teorilerini karşılaştırır", "ANALYSIS", 2)
        ot3 = self._outcome(pool1, "ÖT-3", "Yapılandırmacı yaklaşımı tanımlar", "COMPREHENSION", 3)
        ot4 = self._outcome(pool1, "ÖT-4", "Sosyal öğrenme teorisini uygular", "APPLICATION", 4)

        # ── Havuz 2: Gelişim ve Motivasyon ───────────────────────────────────
        pool2, _ = ItemPool.objects.get_or_create(
            name="Eğitim Psikolojisi — Gelişim ve Motivasyon",
            defaults=dict(
                course="Eğitim Psikolojisi",
                semester="2024-Güz",
                level="Lisans 1",
                owner=user,
                status=ItemPool.Status.ACTIVE,
            ),
        )

        gm1 = self._outcome(pool2, "GM-1", "Bilişsel gelişim dönemlerini sıralar", "KNOWLEDGE", 1)
        gm2 = self._outcome(pool2, "GM-2", "Motivasyon teorilerini karşılaştırır", "ANALYSIS", 2)
        gm3 = self._outcome(pool2, "GM-3", "Öğrenme güçlüklerini tanımlar", "COMPREHENSION", 3)
        gm4 = self._outcome(pool2, "GM-4", "Bireysel farklılıkları değerlendirir", "EVALUATION", 4)

        # ── MCQ Soruları ─────────────────────────────────────────────────────
        self.stdout.write("MCQ soruları oluşturuluyor...")

        p1_mcq = [
            self._mcq(user, pool1, [ot1],
                "Pavlov'un klasik koşullanma deneyinde koşulsuz uyaran hangisidir?",
                [("A","Zil sesi",False),("B","Et tozu",True),("C","Işık",False),("D","Su",False)]),
            self._mcq(user, pool1, [ot1],
                "Operant koşullanmada davranışın tekrarlanma olasılığını artıran süreç nedir?",
                [("A","Ceza",False),("B","Söndürme",False),("C","Pekiştirme",True),("D","Uyarma",False)]),
            self._mcq(user, pool1, [ot2],
                "Vygotsky'nin 'Yakınsak Gelişim Alanı' kavramı neyi ifade eder?",
                [("A","Çocuğun tek başına yapabilecekleri",False),
                 ("B","Yardımla yapabilecekleri ile tek başına yapabilecekleri arasındaki fark",True),
                 ("C","Akranlarla öğrenme",False),
                 ("D","Kalıcı öğrenme alanı",False)]),
            self._mcq(user, pool1, [ot2],
                "Bloom taksonomisinde en üst düzey bilişsel basamak hangisidir?",
                [("A","Analiz",False),("B","Sentez",False),("C","Değerlendirme",True),("D","Hatırlama",False)]),
            self._mcq(user, pool1, [ot4],
                "Bandura'nın sosyal öğrenme teorisine göre öğrenme öncelikle nasıl gerçekleşir?",
                [("A","Deneme-yanılma yoluyla",False),("B","Gözlem yoluyla",True),
                 ("C","Yalnızca pekiştirme ile",False),("D","Ceza yoluyla",False)]),
            self._mcq(user, pool1, [ot3],
                "Yapılandırmacılığa göre bilgi nasıl oluşur?",
                [("A","Aktarım yoluyla",False),("B","Ezber yoluyla",False),
                 ("C","Bireyin deneyimlerini yorumlamasıyla",True),("D","Gözlem yoluyla",False)]),
        ]

        p2_mcq = [
            self._mcq(user, pool2, [gm1],
                "Piaget'e göre 7-11 yaş arası çocuklar hangi bilişsel dönemdedir?",
                [("A","Duyusal-motor",False),("B","İşlem öncesi",False),
                 ("C","Somut işlemler",True),("D","Soyut işlemler",False)]),
            self._mcq(user, pool2, [gm2],
                "Maslow'un ihtiyaçlar hiyerarşisinde en temel basamak hangisidir?",
                [("A","Güvenlik",False),("B","Ait olma",False),
                 ("C","Fizyolojik ihtiyaçlar",True),("D","Saygı",False)]),
            self._mcq(user, pool2, [gm2],
                "İçsel motivasyonun temel kaynağı aşağıdakilerden hangisidir?",
                [("A","Dışsal ödüller",False),("B","Merak ve ilgi",True),
                 ("C","Ceza korkusu",False),("D","Sosyal baskı",False)]),
            self._mcq(user, pool2, [gm3],
                "Okuma güçlüğü olarak tanımlanan öğrenme bozukluğu hangisidir?",
                [("A","Diskalkuli",False),("B","Disfazi",False),
                 ("C","Disleksi",True),("D","Dispraksi",False)]),
            self._mcq(user, pool2, [gm4],
                "Çoklu zeka teorisini geliştiren psikolog kimdir?",
                [("A","Piaget",False),("B","Vygotsky",False),
                 ("C","Gardner",True),("D","Skinner",False)]),
            self._mcq(user, pool2, [gm1],
                "Erikson'un psikososyal gelişim teorisinde kaç evre bulunmaktadır?",
                [("A","4",False),("B","6",False),("C","8",True),("D","10",False)]),
        ]

        # ── TF Soruları ──────────────────────────────────────────────────────
        self.stdout.write("TF soruları oluşturuluyor...")

        p1_tf = [
            self._tf(user, pool1, [ot1],
                "Klasik koşullanmada koşullu uyaran başlangıçta nötr bir uyarandır.", True),
            self._tf(user, pool1, [ot1],
                "Operant koşullanmada ceza uygulamak davranışı kalıcı olarak ortadan kaldırır.", False),
            self._tf(user, pool1, [ot4],
                "Bandura'ya göre gözlemsel öğrenme için pekiştirme zorunlu değildir.", True),
            self._tf(user, pool1, [ot2],
                "Bilişsel teoriler yalnızca gözlemlenebilir davranışlarla ilgilenir.", False),
            self._tf(user, pool1, [ot3],
                "Yapılandırmacılığa göre öğretmenin rolü bilgiyi aktarmaktan çok rehberlik etmektir.", True),
            self._tf(user, pool1, [ot2],
                "Vygotsky, bilişsel gelişimin biyolojik olgunlaşmaya bağımlı olduğunu savunur.", False),
        ]

        p2_tf = [
            self._tf(user, pool2, [gm1],
                "Piaget'e göre bilişsel gelişim evreleri evrensel ve sıralıdır.", True),
            self._tf(user, pool2, [gm2],
                "Dışsal motivasyon her zaman içsel motivasyondan daha etkilidir.", False),
            self._tf(user, pool2, [gm2],
                "Öz-yeterlik inancı yüksek olan öğrenciler akademik başarıda daha iyi sonuçlar alır.", True),
            self._tf(user, pool2, [gm3],
                "DEHB (Dikkat Eksikliği Hiperaktivite Bozukluğu) yalnızca erkek çocuklarda görülür.", False),
            self._tf(user, pool2, [gm4],
                "Öğrencilerin öğrenme stilleri birbirinden farklılık gösterebilir.", True),
            self._tf(user, pool2, [gm1],
                "Vygotsky dil gelişiminin bilişsel gelişimden önce geldiğini öne sürmüştür.", True),
        ]

        # ── SHORT_ANSWER Soruları ────────────────────────────────────────────
        self.stdout.write("Kısa cevaplı sorular oluşturuluyor...")

        p1_sa = [
            self._short(user, pool1, [ot1],
                "Pavlov'un deneyi hangi tür öğrenmeyi açıklamaktadır?",
                "Klasik koşullanma"),
            self._short(user, pool1, [ot1],
                "Skinner'ın kuramında pekiştirmenin kaç temel türü vardır ve bunlar nelerdir?",
                "İki tür: Olumlu pekiştirme (ödül ekleme) ve olumsuz pekiştirme (olumsuz uyaranı kaldırma)"),
            self._short(user, pool1, [ot2],
                "Gestalt psikolojisinin temel ilkesini kısaca açıklayınız.",
                "Bütün, parçaların toplamından fazladır"),
            self._short(user, pool1, [ot2],
                "Miller yasasına göre çalışma belleğinin kapasitesi nedir?",
                "7±2 öge"),
            self._short(user, pool1, [ot4],
                "Bandura'nın gözlemsel öğrenme sürecinin dört temel aşamasını sıralayınız.",
                "Dikkat, hatırlama, motor üretim, güdülenme"),
            self._short(user, pool1, [ot3],
                "Vygotsky'nin 'scaffolding' kavramı ne anlama gelmektedir?",
                "Daha bilgili bireyin öğrenciye sunduğu geçici destek iskele"),
        ]

        p2_sa = [
            self._short(user, pool2, [gm1],
                "Piaget'nin dört bilişsel gelişim dönemini sırasıyla yazınız.",
                "Duyusal-motor, işlem öncesi, somut işlemler, soyut işlemler"),
            self._short(user, pool2, [gm2],
                "Maslow'un ihtiyaçlar hiyerarşisinin en üst basamağı nedir?",
                "Kendini gerçekleştirme"),
            self._short(user, pool2, [gm2],
                "'Öğrenilmiş çaresizlik' kavramını geliştiren psikolog kimdir?",
                "Martin Seligman"),
            self._short(user, pool2, [gm3],
                "Matematik öğrenme güçlüğünün teknik adı nedir?",
                "Diskalkuli"),
            self._short(user, pool2, [gm4],
                "Formative değerlendirme ne zaman uygulanır?",
                "Öğrenme süreci devam ederken (süreç değerlendirmesi)"),
            self._short(user, pool2, [gm1],
                "Erikson'un sekizinci ve son psikososyal gelişim evresinin temel çatışması nedir?",
                "Bütünlük - Umutsuzluk"),
        ]

        # ── OPEN Soruları ────────────────────────────────────────────────────
        self.stdout.write("Açık uçlu sorular oluşturuluyor...")

        p1_open = [
            self._open(user, pool1, [ot1, ot2],
                "Davranışçı ve bilişsel öğrenme teorilerini temel varsayımlar açısından karşılaştırınız.",
                "Davranışçılık (gözlenebilir davranış, pekiştirme), bilişselcilik (zihinsel süreçler, şema) karşılaştırılmalı; her ikisine örnek verilmeli. (20 puan)"),
            self._open(user, pool1, [ot3],
                "Yapılandırmacı öğrenme yaklaşımının sınıf ortamına yansımalarını somut örneklerle tartışınız.",
                "Proje tabanlı öğrenme, işbirlikli öğrenme, keşfederek öğrenme örnekleri verilmeli. (20 puan)"),
            self._open(user, pool1, [ot4],
                "Bandura'nın sosyal öğrenme teorisinin sınıf yönetimindeki uygulamalarını değerlendiriniz.",
                "Model olma, öz-yeterlik, öz-düzenleme kavramları ve sınıf uygulamaları açıklanmalı. (20 puan)"),
            self._open(user, pool1, [ot2],
                "Bloom taksonomisinin eğitim hedefleri yazımındaki önemini açıklayınız ve her basamak için ölçme sorusu örneği veriniz.",
                "Altı basamak açıklanmalı; her basamak için uygun fiil kullanılarak örnek hedef/soru yazılmalı. (20 puan)"),
            self._open(user, pool1, [ot1, ot3],
                "Öğrencilerin kalıcı öğrenmesini sağlamak için hangi öğrenme teorilerinden yararlanırsınız? Gerekçenizi açıklayınız.",
                "En az iki teoriye atıfta bulunulmalı; teorik gerekçe ile pratik strateji birleştirilmeli. (20 puan)"),
        ]

        p2_open = [
            self._open(user, pool2, [gm1],
                "Piaget ve Vygotsky'nin bilişsel gelişim görüşlerini karşılaştırarak eğitime yansımalarını tartışınız.",
                "Piaget (özümleme, uyum, denge) ve Vygotsky (ZGA, scaffolding) karşılaştırılmalı; sınıf uygulamaları verilmeli. (25 puan)"),
            self._open(user, pool2, [gm2],
                "İçsel ve dışsal motivasyonun akademik başarıya etkisini araştırma bulgularıyla destekleyerek tartışınız.",
                "Deci & Ryan'ın öz-belirleme teorisi dahil en az iki araştırmaya atıf; içsel motivasyonu artırma stratejileri. (25 puan)"),
            self._open(user, pool2, [gm3],
                "Özel eğitim ihtiyacı olan öğrencilerin kaynaştırma eğitimindeki başarısını artırmak için uygulayacağınız stratejileri açıklayınız.",
                "Bireyselleştirilmiş eğitim planı, evrensel tasarım, akran desteği, aile iş birliği stratejileri ele alınmalı. (25 puan)"),
            self._open(user, pool2, [gm4],
                "Gardner'ın çoklu zeka teorisinin sınıf uygulamalarında nasıl kullanılabileceğini açıklayınız.",
                "En az 5 zeka türü açıklanmalı; her biri için somut sınıf etkinliği örneği verilmeli. (25 puan)"),
            self._open(user, pool2, [gm1, gm2],
                "Erikson'un psikososyal gelişim teorisinin okul dönemine (6-18 yaş) denk gelen evrelerini ve bu evrelerin eğitime yansımalarını açıklayınız.",
                "Endüstriyelik-aşağılık ve kimlik-rol karmaşası evreleri; öğretmenin rolü, kimlik oluşumu stratejileri. (25 puan)"),
        ]

        # ── Test Formları ────────────────────────────────────────────────────
        self.stdout.write("Sınav formları oluşturuluyor...")
        all_instances_p1 = list(ItemInstance.objects.filter(pool=pool1))
        all_instances_p2 = list(ItemInstance.objects.filter(pool=pool2))

        def get_by_type(instances, item_type):
            return [i for i in instances if i.item.item_type == item_type]

        def make_form(name, pool, p1_mcq_n, p2_mcq_n, p1_tf_n, p2_tf_n,
                      p1_sa_n, p2_sa_n, p1_open_n, p2_open_n):
            tf_obj, created = TestForm.objects.get_or_create(
                name=name, pool=pool,
                defaults=dict(created_by=user),
            )
            if not created:
                return tf_obj
            order = 1
            for inst, n in [
                (get_by_type(all_instances_p1, 'MCQ'), p1_mcq_n),
                (get_by_type(all_instances_p2, 'MCQ'), p2_mcq_n),
                (get_by_type(all_instances_p1, 'TF'),  p1_tf_n),
                (get_by_type(all_instances_p2, 'TF'),  p2_tf_n),
                (get_by_type(all_instances_p1, 'SHORT_ANSWER'), p1_sa_n),
                (get_by_type(all_instances_p2, 'SHORT_ANSWER'), p2_sa_n),
                (get_by_type(all_instances_p1, 'OPEN'), p1_open_n),
                (get_by_type(all_instances_p2, 'OPEN'), p2_open_n),
            ]:
                for item_inst in inst[:n]:
                    pts = 5 if item_inst.item.item_type in ('MCQ', 'TF') else \
                          10 if item_inst.item.item_type == 'SHORT_ANSWER' else 20
                    FormItem.objects.create(
                        form=tf_obj, item_instance=item_inst, order=order, points=pts)
                    order += 1
            return tf_obj

        vize = make_form(
            "Eğitim Psikolojisi Vize Sınavı 2024-Güz", pool1,
            p1_mcq_n=5, p2_mcq_n=5, p1_tf_n=3, p2_tf_n=3,
            p1_sa_n=2, p2_sa_n=2, p1_open_n=1, p2_open_n=1,
        )
        final = make_form(
            "Eğitim Psikolojisi Final Sınavı 2024-Güz", pool1,
            p1_mcq_n=6, p2_mcq_n=6, p1_tf_n=4, p2_tf_n=4,
            p1_sa_n=3, p2_sa_n=3, p1_open_n=2, p2_open_n=2,
        )
        butunleme = make_form(
            "Eğitim Psikolojisi Bütünleme Sınavı 2024-Güz", pool2,
            p1_mcq_n=5, p2_mcq_n=5, p1_tf_n=3, p2_tf_n=3,
            p1_sa_n=2, p2_sa_n=2, p1_open_n=2, p2_open_n=2,
        )

        self.stdout.write(f"  Vize:       {vize.form_items.count()} soru")
        self.stdout.write(f"  Final:      {final.form_items.count()} soru")
        self.stdout.write(f"  Bütünleme:  {butunleme.form_items.count()} soru")

        # ── PDF Üretimi ──────────────────────────────────────────────────────
        self.stdout.write("PDF'ler oluşturuluyor...")
        out_dir = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "..", "sample_pdfs"
        )
        os.makedirs(out_dir, exist_ok=True)

        for form, form_slug in [(vize, "vize"), (final, "final"), (butunleme, "butunleme")]:
            for tmpl in templates:
                slug = tmpl.name.replace(" ", "_").replace("(", "").replace(")", "").lower()
                filename = f"{form_slug}_{slug}.pdf"
                path = os.path.join(out_dir, filename)
                try:
                    pdf_bytes = generate_exam_pdf(form, tmpl, with_answer_key=True)
                    with open(path, "wb") as f:
                        f.write(pdf_bytes)
                    self.stdout.write(f"  ✓ {filename} ({len(pdf_bytes)//1024} KB)")
                except Exception as e:
                    self.stdout.write(self.style.WARNING(f"  ✗ {filename}: {e}"))

        self.stdout.write(self.style.SUCCESS("Tamamlandı!"))

    # ── Yardımcı metodlar ─────────────────────────────────────────────────────

    def _outcome(self, pool, code, description, level, order):
        from itempool.models import LearningOutcome
        obj, _ = LearningOutcome.objects.get_or_create(
            pool=pool, code=code,
            defaults=dict(description=description, level=level, order=order, is_active=True),
        )
        return obj

    def _mcq(self, user, pool, outcomes, stem, choices):
        from itempool.models import Item, ItemChoice, ItemInstance
        item, created = Item.objects.get_or_create(
            stem=stem, item_type='MCQ',
            defaults=dict(author=user, max_choices=len(choices),
                          status=Item.Status.ACTIVE),
        )
        if created:
            for label, text, correct in choices:
                ItemChoice.objects.create(
                    item=item, label=label, text=text,
                    is_correct=correct, order=ord(label) - ord('A'),
                )
        inst, _ = ItemInstance.objects.get_or_create(pool=pool, item=item,
                                                      defaults=dict(added_by=user))
        inst.learning_outcomes.set(outcomes)
        return inst

    def _tf(self, user, pool, outcomes, stem, correct_is_true):
        from itempool.models import Item, ItemChoice, ItemInstance
        item, created = Item.objects.get_or_create(
            stem=stem, item_type='TF',
            defaults=dict(author=user, max_choices=2,
                          status=Item.Status.ACTIVE),
        )
        if created:
            ItemChoice.objects.create(item=item, label='A', text='Doğru',
                                      is_correct=correct_is_true, order=0)
            ItemChoice.objects.create(item=item, label='B', text='Yanlış',
                                      is_correct=not correct_is_true, order=1)
        inst, _ = ItemInstance.objects.get_or_create(pool=pool, item=item,
                                                      defaults=dict(added_by=user))
        inst.learning_outcomes.set(outcomes)
        return inst

    def _short(self, user, pool, outcomes, stem, expected_answer):
        from itempool.models import Item, ItemInstance
        item, _ = Item.objects.get_or_create(
            stem=stem, item_type='SHORT_ANSWER',
            defaults=dict(author=user, expected_answer=expected_answer,
                          status=Item.Status.ACTIVE),
        )
        inst, _ = ItemInstance.objects.get_or_create(pool=pool, item=item,
                                                      defaults=dict(added_by=user))
        inst.learning_outcomes.set(outcomes)
        return inst

    def _open(self, user, pool, outcomes, stem, scoring_rubric):
        from itempool.models import Item, ItemInstance
        item, _ = Item.objects.get_or_create(
            stem=stem, item_type='OPEN',
            defaults=dict(author=user, scoring_rubric=scoring_rubric,
                          status=Item.Status.ACTIVE),
        )
        inst, _ = ItemInstance.objects.get_or_create(pool=pool, item=item,
                                                      defaults=dict(added_by=user))
        inst.learning_outcomes.set(outcomes)
        return inst
