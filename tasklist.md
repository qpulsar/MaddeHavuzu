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
