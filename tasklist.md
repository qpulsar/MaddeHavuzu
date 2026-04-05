# Madde Havuzu ve Test Sistemi — Detaylı Görev Listesi

> **Referans proje:** `nefoptik_ref/` (Django 4.2+ optik form değerlendirme sistemi)
> **Yeni proje adı:** MaddeHavuzu
> **Tech stack:** Django 4.2+ · DRF · PostgreSQL (dev: SQLite) · Vanilla JS · Bootstrap 5

---

## Faz 0 — Proje İskeleti ve Altyapı

- [x] **F0.1** GitHub fork & repo başlatma
  - [x] `qpulsar/nefoptik` reposunu fork'la → `MaddeHavuzu` olarak adlandır
  - [x] Yerel klonu workspace'e taşı, `.git` remote'ları güncelle
  - [x] `.env.example` güncelle (yeni proje değişkenleri)
- [x] **F0.2** Django proje yapılandırması
  - [x] `optikform` → `maddehavuzu` proje adı refactor
  - [x] `grading` uygulamasını koru + yeni `itempool` Django app'i oluştur
  - [x] `requirements.txt` güncelle: `python-docx`, `djangorestframework`, `django-filter`, `openai` (veya LLM client)
  - [x] `settings.py` güncelle: `REST_FRAMEWORK` config, yeni app kayıtları
- [x] **F0.3** Veritabanı yapılandırması
  - [x] Development SQLite, Production PostgreSQL seçimi koru
  - [x] İlk migration planını hazırla
- [x] **F0.4** Statik dosyalar ve tema
  - [x] NefOptik'in mevcut Bootstrap temasını refactor et
  - [x] Sidebar menüyü yeni modüllere göre güncelle
  - [ ] Renk skalası CSS değişkenleri tanımla (risk skoru için)
- [x] **F0.5** CI/CD ve test altyapısı
  - [x] `pytest` + `pytest-django` kurulumu
  - [x] Test dizin yapısı oluştur: `tests/unit/`, `tests/integration/`
  - [x] GitHub Actions temel pipeline (lint + test)

---

## Faz 1 — Madde Havuzu Yönetimi (Çekirdek)

### 1.1 Havuz (ItemPool) CRUD
- [x] **F1.1.1** Model: `ItemPool`
  - [x] Alanlar: `name`, `course`, `semester`, `level` (Lisans1/2, YL), `tags`, `status` (ACTIVE/ARCHIVED), `owner`, `created_at`, `updated_at`
  - [x] Migration oluştur ve çalıştır
- [x] **F1.1.2** View: `ItemPoolListView`, `ItemPoolCreateView`, `ItemPoolUpdateView`, `ItemPoolArchiveView`
- [x] **F1.1.3** Template: `pool_list.html`, `pool_form.html`, `pool_detail.html`
- [x] **F1.1.4** URL tanımlamaları ve sidebar menü entegrasyonu
- [x] **F1.1.5** Yetkilendirme: havuz sahibi + koordinatör erişimi
- [x] **F1.1.6** Unit testler: CRUD operasyonları

### 1.2 Öğrenme Çıktısı (LearningOutcome) Yönetimi
- [x] **F1.2.1** Model: `LearningOutcome`
  - [x] Alanlar: `pool` (FK), `code`, `description`, `level` (Bloom taksonomisi), `weight` (opsiyonel), `order`, `is_active`
  - [x] Migration
- [x] **F1.2.2** Havuz detay sayfasında inline CRUD (HTMX/JS)
- [x] **F1.2.3** API endpoint: `GET/POST /api/pools/{id}/outcomes/`
- [x] **F1.2.4** Unit testler

### 1.3 Madde (Item) Modeli — Merkezi Yapı
- [x] **F1.3.1** Model: `Item` (merkezi madde)
  - [x] Alanlar: `stem` (madde kökü), `item_type` (MCQ/TF/MATCHING/OPEN), `difficulty_intended`, `author`, `created_at`, `updated_at`, `version`, `status` (DRAFT/ACTIVE/RETIRED)
- [x] **F1.3.2** Model: `ItemChoice` (şıklar — MCQ için)
  - [x] Alanlar: `item` (FK), `label` (A/B/C/D/E), `text`, `is_correct`, `order`
- [x] **F1.3.3** Model: `ItemInstance` (havuz-madde ilişkisi)
  - [x] Alanlar: `pool` (FK), `item` (FK), `learning_outcomes` (M2M), `is_fork` (kopyalandı mı?), `forked_from` (self FK), `added_at`, `added_by`
  - [x] Unique constraint: `(pool, item)` — aynı havuzda aynı madde iki kez olamaz
- [x] **F1.3.4** Migration ve indexler
- [x] **F1.3.5** Unit testler: madde oluşturma, referanslama vs fork

- [x] **F1.4.1** Madde oluşturma formu
- [x] **F1.4.2** Madde listeleme (havuz detay sayfasında)
- [x] **F1.4.3** Madde düzenleme ve silme (soft-delete)
- [x] **F1.4.4** Madde detay sayfası: analiz sonuçları paneli
- [x] **F1.4.5** Sürüm geçmişi görüntüleme
- [x] **F1.4.6** Unit ve integration testler

---

## Faz 2 — Word'den Toplu Madde Yükleme (Docx Import)

### 2.1 Docx Parser Servisi
- [x] **F2.1.1** `python-docx` ile parse servisi: `services/import_docx.py`
- [x] **F2.1.2** Model: `DraftItem`
- [x] **F2.1.3** Model: `ImportBatch`
- [x] **F2.1.4** Unit testler

### 2.2 Import Akışı UI
- [x] **F2.2.1** Dosya yükleme sayfası: `import_upload.html`
- [x] **F2.2.2** Önizleme sayfası: `import_preview.html`
- [x] **F2.2.3** Onay ve commit
- [x] **F2.2.4** DRF endpoints

### 2.3 AI Destekli İyileştirmeler (Import Sırasında)
- [x] **F2.3.1** LLM Client arayüzü: `services/llm_client.py`
- [x] **F2.3.2** Madde kökü/şık dil temizliği önerisi
- [x] **F2.3.3** Öğrenme çıktısı önerisi
- [x] **F2.3.4** AI önerilerinin `DraftItem`'a eklenmesi

---

## Faz 3 — AI Öğrenme Çıktısı Eşleme

### 3.1 Öneri Motoru
- [x] **F3.1.1** Model: `OutcomeSuggestion`
  - [x] `item` (FK), `learning_outcome` (FK), `score` (0-1), `reasoning`, `status` (PENDING/ACCEPTED/REJECTED), `created_at`
- [x] **F3.1.2** Servis: `services/llm_client.py` (ve `GeminiClient`)
  - [x] `suggest_outcomes(item_text, outcomes_list)` → top 1-3 eşleşme + skor + gerekçe
  - [x] LLMClient kullanarak eşleme (Gemini 1.5 Flash)
- [x] **F3.1.3** HTMX/View endpoints
  - [x] `GET /items/{id}/suggest-outcomes/` → önerileri al
  - [x] `POST /items/assign-outcome/` → kullanıcı onayı ile ata

### 3.2 UI Entegrasyonu
- [x] **F3.2.1** Madde detay sayfasında "AI Öneri" paneli
  - [x] Öneriler liste halinde (skor + gerekçe gösterilir)
  - [x] Kullanıcı seçip "Onayla" der
- [x] **F3.2.2** Toplu öneri: havuz bazında tüm maddelere AI önerisi çalıştır

---

## Faz 4 — Madde Analizi ve Görünürlük

### 4.1 Analiz Sonuç Modelleri
- [x] **F4.1.1** Model: `ItemAnalysisResult`
- [x] **F4.1.2** İstatistik servisi entegrasyonu: `analysis_service.py`
- [x] **F4.1.3** Unit testler (Model ve servis metodları için)
- [x] **F4.2.1** `risk_score()` fonksiyonu ve sınıfları
- [x] **F4.2.2** CSS renk skalası ve Bootstrap entegrasyonu
- [x] **F4.2.3** Madde listesinde ve detayında risk gösterimi
- [x] **F4.3.1** Madde detay sayfasında analiz özeti

---

## Faz 5 — Test Formu Oluşturma (Blueprint + Belirtke Tablosu)

### 5.1 Form Modelleri
- [x] **F5.1.1** Model: `TestForm`
- [x] **F5.1.2** Model: `FormItem`
- [x] **F5.1.3** Model: `Blueprint`
- [x] **F5.1.4** Model: `SpecificationTable`
- [x] **F5.1.6** Migration ve indexler

### 5.2 Form Oluşturma Sihirbazı (Wizard UI)
- [x] **F5.2.1** Adım 1: Havuz seçimi (zorunlu)
- [x] **F5.2.2** Adım 2: Ayarlar
- [x] **F5.2.3** Adım 3: Madde seçimi (Manuel & Blueprint)
- [x] **F5.2.4** Adım 4: Önizleme + kaydet
- [x] **F5.2.5** Backend: `FormCreateService` (View içi logic)

### 5.3 Form CRUD ve Listeleme
- [x] **F5.3.1** Form listesi (havuz bazında)
- [x] **F5.3.2** Form detay: madde listesi, istatistikler
- [x] **F5.3.3** Form düzenleme (madde ekleme/çıkarma)
- [x] **F5.3.4** Blueprint kopyalama/klonlama
- [x] **F5.3.5** Unit ve integration testler

---

## Faz 6 — Test ve Madde Analizi Entegrasyonu

### 6.1 Veri Okuma Akışı
- [x] **F6.1.1** NefOptik parser'ını koru ve genişlet
  - [x] Mevcut `ConfigurableParser` + `ParsingService` aynen kalacak
  - [x] Yeni akış: önce havuz → sonra form seçimi ile ilişkilendirme
- [x] **F6.1.2** View: `AnalysisDataUploadView`
  - [x] Havuz seçimi (1. adım)
  - [x] Form seçimi (2. adım, opsiyonel: yeni form oluştur)
- [x] **F6.1.3** Yanıt anahtarı eşleme
  - [x] Formun maddeleri ile optik okuyucu soru sırası eşleştirilecek
  - [x] Eşleşme uyumsuzluğu uyarıları

### 6.2 Analiz Sonuçlarını DB'ye Aktırma
- [x] **F6.2.1** Maddeler bazında istatistik hesaplama
  - [x] NefOptik `StatisticsService._calculate_item_analysis()` kullanılacak
  - [x] Her madde için `ItemAnalysisResult` kaydı oluşturulacak
- [x] **F6.2.2** "Analizi DB'ye Aktar" butonu ve akışı
- [x] **F6.2.3** Analiz geçmişi: aynı maddenin farklı uygulamalardaki sonuçları

### 6.3 Entegre Görünümler
- [x] **F6.3.1** Test Formları menüsü altında "Test ve Madde Analizi" alt menüsü
- [x] **F6.3.2** Madde detay sayfasında analiz geçmişi gösterimi
- [x] **F6.3.3** Form detay sayfasında toplu analiz özeti
- [x] **F6.3.4** Unit ve integration testler

---

## Faz 7 — Yetkilendirme ve Kullanıcı Yönetimi

- [x] **F7.1** NefOptik'in mevcut kullanıcı modelini genişlet
  - [x] Roller: `INSTRUCTOR`, `COORDINATOR`, `ASSISTANT`, `ADMIN`
  - [x] `UserProfile` → `role` alanı ekle
- [x] **F7.2** Havuz bazlı erişim kontrolü
  - [x] `PoolPermission` modeli: `user`, `pool`, `permission_level`
  - [x] Mixin: `PoolAccessMixin`
- [x] **F7.3** Ders/dönem bazlı yetki filtreleme
- [x] **F7.4** Admin dashboard genişletme: havuz istatistikleri, kullanıcı aktivitesi
- [x] **F7.5** Unit testler: yetki kontrolleri

---

## Faz 8 — Fonksiyonel Olmayan Gereksinimler

- [x] **F8.1** İzlenebilirlik (Audit Trail)
  - [x] `ItemAuditLog` modeli: `item`, `action`, `user`, `timestamp`, `details_json`
  - [x] Her madde düzenlemesinde log kaydı
  - [x] Hangi formda kullanıldı bilgisi
- [x] **F8.2** Performans
  - [x] Word import ve analiz sonuçları için pagination
  - [x] Madde listesi için DB index optimizasyonu
  - [x] Büyük havuzlar için select_related/prefetch_related
- [x] **F8.3** Güvenlik
  - [x] Dosya yükleme: boyut limiti, uzantı kontrolü, MIME check
  - [x] CSRF, XSS korumaları (Django default + ek kontroller)
  - [x] API rate limiting
- [x] **F8.4** Denetlenebilirlik
  - [x] Analiz değerlerinin hangi veri setinden üretildiği tracing
  - [x] Import batch → madde → analiz kaydı ilişki zinciri

---

## Faz 9 — Son Kontroller ve Deployment

- [x] **F9.1** Tüm testlerin çalıştığını doğrula
- [x] **F9.2** README.md güncelle
- [x] **F9.3** Deployment konfigürasyonu
  - [x] Production settings
  - [x] Docker Compose (opsiyonel)
  - [x] Static files collection
- [x] **F9.4** Kullanıcı kılavuzu / yardım sayfası
- [x] **F9.5** Son kullanıcı testi ve geri bildirim

---

## Faz 10 — Soru Modeli Genişletme

### 10.1 Item Tipi ve Ek Alanlar
- [x] **F10.1.1** `Item.ItemType`'a `SHORT_ANSWER` (Kısa Cevaplı) tipi ekle
- [x] **F10.1.2** `Item` modeline `expected_answer` alanı ekle (SHORT_ANSWER için beklenen cevap)
- [x] **F10.1.3** `Item` modeline `scoring_rubric` alanı ekle (OPEN_ENDED için puanlama kılavuzu)
- [x] **F10.1.4** Migration

### 10.2 MCQ Dinamik Seçenek Sayısı
- [x] **F10.2.1** `ItemChoice.clean()` validasyonu: MCQ için min 2, max 10 şık zorla
- [x] **F10.2.2** `ItemChoice.label` help_text güncelle; A-J (10 seçenek) destekleniyor yap
- [x] **F10.2.3** `Item` modeline `max_choices` field ekle (varsayılan 4, 2-10 arası)

### 10.3 UI Güncellemeleri
- [x] **F10.3.1** Madde oluşturma formu (`item_form.html`): soru tipine göre dinamik alan göster/gizle (JS)
- [x] **F10.3.2** MCQ formunda dinamik şık ekle/çıkar butonu (2-10 arası)
- [x] **F10.3.3** SHORT_ANSWER için beklenen cevap alanı göster
- [x] **F10.3.4** OPEN_ENDED için puanlama kılavuzu (scoring_rubric) textarea göster
- [x] **F10.3.5** Madde detay sayfasında yeni alanları göster

### 10.4 Testler
- [x] **F10.4.1** Model validasyon testleri (SHORT_ANSWER, seçenek sayısı limitleri)
- [x] **F10.4.2** View testleri (farklı soru tipleri için form gönderimi)

---

## Faz 11 — Sınav Uygulama ve Grup Yönetimi

### 11.1 Öğrenci Grubu Modeli
- [x] **F11.1.1** Model: `StudentGroup` (ad, dönem, ders, açıklama)
- [x] **F11.1.2** CRUD view ve şablonları (`studentgroup_list.html`, `studentgroup_form.html`)
- [x] **F11.1.3** Migration ve URL tanımlamaları

### 11.2 Sınav Uygulama Modeli
- [x] **F11.2.1** Model: `ExamApplication` (`TestForm` FK, `StudentGroup` FK, `applied_at`, `notes`)
- [x] **F11.2.2** `UploadSession`'a `exam_application` FK ekle (opsiyonel, grading entegrasyonu için)
- [x] **F11.2.3** CRUD view ve şablonları
- [x] **F11.2.4** Migration

### 11.3 Soru Tekrar Etmeme
- [x] **F11.3.1** Servis: bir gruba daha önce uygulanmış soruların `ItemInstance` ID listesini döndür
- [x] **F11.3.2** Test formu oluşturma sihirbazında "bu gruba daha önce sorulmuş soruları dışla" filtresi
- [x] **F11.3.3** Madde seçim ekranında "tekrar eden soru" uyarısı göster

### 11.4 Testler
- [x] **F11.4.1** Model testleri (StudentGroup, ExamApplication)
- [x] **F11.4.2** Soru tekrar filtresi mantığı testleri

---

## Faz 12 — Sınav Kağıdı Oluşturma (PDF)

### 12a — Sayfa Düzeni Şablonu
- [x] **F12a.1** Model: `ExamTemplate` (sütun sayısı 1-3, sütun arası çizgi, font, satır aralığı, kenar boşlukları, başlık/altbilgi alanları)
- [x] **F12a.2** `requirements.txt`'e `weasyprint` ekle
- [x] **F12a.3** Varsayılan şablon seed verisi (5 hazır şablon: Standart, 2 Sütun, Yoğun, Geniş Kenar, Sade)
- [x] **F12a.4** Şablon CRUD view ve şablonları
- [x] **F12a.5** Migration

### 12b — PDF Üretimi
- [x] **F12b.1** `ExamPdfService`: `TestForm` + `ExamTemplate` → PDF üretim servisi
- [x] **F12b.2** Django HTML şablonu (`exam_print.html`): CSS sütun düzeni, WeasyPrint uyumlu
- [x] **F12b.3** A4/A5 sayfa boyutu ve kenar boşluğu desteği
- [x] **F12b.4** Öğretmen kopyası: cevap anahtarı sayfası ekle
- [x] **F12b.5** Cevap kâğıdı / boş form seçeneği (opsiyonel)

### 12c — UI
- [x] **F12c.1** Test formu detay sayfasına "Sınav Kağıdı Oluştur" butonu ekle
- [x] **F12c.2** Şablon seçimi + önizleme modalı
- [x] **F12c.3** PDF indirme endpoint (`/formlar/<pk>/pdf/`)
- [x] **F12c.4** URL tanımlamaları

### 12d — Testler
- [x] **F12d.1** `ExamPdfService` testleri (PDF üretimi başarı/hata senaryoları)
- [x] **F12d.2** Şablon CRUD testleri

---

## Faz 13 — Değerlendirme Entegrasyonu Güçlendirme

### 13.1 TestForm ↔ UploadSession Bağlantısı
- [x] **F13.1.1** `UploadSession` modeline `test_form` FK ekle (opsiyonel, `grading` → `itempool`)
- [x] **F13.1.2** Grading yükleme formunda TestForm seçimi
- [x] **F13.1.3** Migration

### 13.2 Otomatik Cevap Anahtarı
- [x] **F13.2.1** `TestForm`dan cevap anahtarı üretim servisi (`FormToAnswerKeyService`)
- [x] **F13.2.2** `UploadSession.answer_key` alanına otomatik aktarım
- [x] **F13.2.3** Cevap anahtarı uyuşmazlığı (soru sayısı farklı) uyarısı

### 13.3 Öğrenme Çıktısı Bazında Başarı Raporu
- [x] **F13.3.1** `FormItem` ↔ `LearningOutcome` üzerinden çıktı bazında doğru/yanlış hesaplama servisi
- [x] **F13.3.2** Öğrenme çıktısı başarı raporu view ve template
- [x] **F13.3.3** Sınıf ortalaması + zayıf/güçlü çıktı görselleştirmesi (Bootstrap progress bar)

### 13.4 Grup Karşılaştırma Raporu
- [x] **F13.4.1** Aynı `TestForm`u alan farklı grupların karşılaştırmalı istatistikleri (ortalama, standart sapma)
- [x] **F13.4.2** Karşılaştırma raporu view ve template

### 13.5 Testler
- [x] **F13.5.1** Cevap anahtarı aktarım testleri
- [x] **F13.5.2** Öğrenme çıktısı raporu hesaplama testleri

---

## Faz 14 — AI Madde Üretimi ve Geliştirme

### 14.1 Kazanım Bazlı Otomatik Soru Üretimi
- [x] **F14.1.1** `GeminiClient` genişletme: `generate_item(outcome, difficulty)` metodu
- [x] **F14.1.2** UI: Kazanım detay sayfasında "AI ile Soru Üret" butonu ve modalı
- [x] **F14.1.3** Üretilen sorunun `DraftItem` olarak sisteme kaydedilmesi
- [x] **F14.1.4** Birden fazla alternatif soru üretme ve seçme arayüzü

### 14.2 Çeldirici ve Varyasyon Oluşturma
- [x] **F14.2.1** Mevcut soru köküne göre "Mantıklı Çeldirici" (Distractor) öneri servisi
- [x] **F14.2.2** Soru varyasyon oluşturucu (Clone with variation): Sayısal verileri veya bağlamı değiştirme
- [x] **F14.2.3** AI Redaksiyon: Dil bilgisi, netlik ve sınav tekniği kontrolü (`suggest_improvements` geliştirme)

### 14.3 Prompt Mühendisliği ve Şablonlar
- [x] **F14.3.1** Soru tipi bazlı (MCQ, Short Answer) özel prompt şablonları
- [x] **F14.3.2** Bloom taksonomisi seviyelerine göre zorluk derecelendirme promptları

---

## Faz 15 — Benzerlik Analizi ve Vektör Arama

### 15.1 Vektör Altyapısı (Embeddings)
- [ ] **F15.1.1** `GeminiClient` veya `Sentence-Transformers` ile embedding üretim servisi
- [ ] **F15.1.2** `Item` modeli için `embedding` alanı (veya PostgreSQL kullanılıyorsa `pgvector` entegrasyonu)
- [ ] **F15.1.3** Mevcut tüm maddelerin vektörlerinin arka planda (celery/task) çıkarılması

### 15.2 Mükerrer Kontrolü ve Arama
- [ ] **F15.2.1** Soru oluşturma/import sırasında "Benzer Soru Var" uyarısı (Threshold tabanlı)
- [ ] **F15.2.2** Anlamsal (Semantic) arama arayüzü: Anahtar kelime yerine anlama göre soru bulma
- [ ] **F15.2.3** Benzer soruları "Grup" olarak işaretleme veya birleştirme önerisi

---

---

## Faz 16 — Gelişmiş Görsel Analiz Dashboard

### 16.1 Görselleştirme Altyapısı
- [ ] **F16.1.1** Frontend kütüphanesi seçimi ve entegrasyonu (`Chart.js` veya `ECharts`)
- [ ] **F16.1.2** Analiz verilerini JSON formatında dönen API endpoint'leri

### 16.2 Havuz ve Sınav İstatistikleri
- [ ] **F16.2.1** Havuz Sağlık Dashboard'u: Zorluk dağılımı (Bar), Ayırt edicilik (Scatter), Kazanım kapsama (Radar)
- [ ] **F16.2.2** Sınav Sonrası Analiz Paneli: KR-20, Cronbach Alpha ve madde analizlerinin grafiksel gösterimi
- [ ] **F16.2.3** Riskli soruların (çok kolay/zor veya negatif ayırt edicilik) otomatik listelenmesi

### 16.3 Kazanım Bazlı Başarı Isı Haritası (Heatmap)
- [ ] **F16.3.1** Sınıfın hangi kazanımlarda zayıf/güçlü olduğunu gösteren ısı haritası
- [ ] **F16.3.2** Branş/Dönem bazlı karşılaştırmalı başarı grafikleri

---

---

## Faz 18 — Word (.docx) Tabanlı Sınav Başlığı Desteği
- [x] **F18.1.1** `ExamTemplate` modeline `header_html` eklenmesi
- [x] **F18.2.1** `DocxHeaderService` (Word to HTML/Base64 conversion)
- [x] **F18.3.1** UI: Word dosyası yükleme ve önbelleğe alma
- [x] **F18.4.1** PDF Resolve: Harf duyarlı (case-sensitive) değişken desteği

---

## Faz 19 — Soru Onay ve Revizyon Akışı (Workflow)

### 17.1 Durum Yönetimi ve Yetkilendirme
- [ ] **F17.1.1** `Item.status` genişletme: `DRAFT`, `IN_REVIEW`, `APPROVED`, `REJECTED`, `REVISION_REQUESTED`
- [ ] **F17.1.2** Onay yetkisi (COORDINATOR) ve Editör rolleri için özel görünümler

### 17.2 İnceleme ve Geri Bildirim Sistemi
- [ ] **F17.2.1** Soru özelinde yorum/geri bildirim bırakma sistemi (In-line feedback)
- [ ] **F17.2.2** Değişiklik geçmişi (Diff view): Eski sürüm ile yeni sürüm arasındaki farkları görme
- [ ] **F17.2.3** Onay/Red durumlarında yazara bildirim gönderilmesi (Dashboard alert)

### 17.3 Envanter Yönetimi
- [ ] **F17.3.1** Soru kullanım kotası ve "Soru Yorgunluğu" takibi (Son X yılda Y kez kullanıldı uyarısı)
- [ ] **F17.3.2** Havuz bazlı revizyon raporları (Hangi sorular güncellenmeli?)

---


## Notlar

### NefOptik'ten Devralınan Modüller
| Modül | Durum | Açıklama |
|-------|-------|----------|
| `UserProfile` + onay sistemi | **Koru & Genişlet** | Rol alanı eklenecek |
| `FileFormatConfig` | **Aynen Koru** | Optik okuyucu format tanımları |
| `UploadSession` + `StudentResult` | **Koru & İlişkilendir** | Havuz/Form bağı eklenecek |
| `ParsingService` + `ConfigurableParser` | **Aynen Koru** | TXT parse altyapısı |
| `GradingService` | **Aynen Koru** | Notlama motoru |
| `StatisticsService` | **Genişlet** | Madde analizi metrikleri eklenecek |
| `CheatingAnalysisService` | **Aynen Koru** | Kopya analizi |
| `ExportService` (xlsx) | **Koru & Genişlet** | Analiz sonuçları dahil |

### Gerekli MCP ve Araçlar
- ✅ `sequential-thinking` MCP — Planlama ve tasarım kararları için
- ❌ `filesystem` MCP — Yüklü değil (dosya yönetimi araçları zaten mevcut)
- ❌ `github` MCP — Yüklü değil → **Yüklenirse**: fork, PR, issue yönetimi kolaylaşır
- ❌ `postgres` MCP — Yüklü değil → **Yüklenirse**: DB sorguları için faydalı
- ❌ Django / Python skill — Yüklü değil → Not aldım

### Kritik Tasarım Kararları
1. **Item + ItemInstance**: Aynı madde birden çok havuzda referanslanabilir, fork mekanizması ile sürümleme
2. **Tek adımlı form kaydı**: Atomik transaction ile sihirbaz akışı
3. **AI önerileri = sadece öneri**: Otomatik kayıt yok, kullanıcı onayı zorunlu
4. **Risk skoru formülü**: Ağırlıklı ortalama (zorluk + ayırt edicilik + çeldirici verimliliği)
