# Madde Havuzu ve Test Sistemi — Detaylı Görev Listesi

> **Referans proje:** `nefoptik_ref/` (Django 4.2+ optik form değerlendirme sistemi)
> **Yeni proje adı:** MaddeHavuzu
> **Tech stack:** Django 4.2+ · DRF · PostgreSQL (dev: SQLite) · Vanilla JS · Bootstrap 5

---

## Faz 0 — Proje İskeleti ve Altyapı

- [ ] **F0.1** GitHub fork & repo başlatma
  - [ ] `qpulsar/nefoptik` reposunu fork'la → `MaddeHavuzu` olarak adlandır
  - [ ] Yerel klonu workspace'e taşı, `.git` remote'ları güncelle
  - [ ] `.env.example` güncelle (yeni proje değişkenleri)
- [ ] **F0.2** Django proje yapılandırması
  - [ ] `optikform` → `maddehavuzu` proje adı refactor
  - [ ] `grading` uygulamasını koru + yeni `itempool` Django app'i oluştur
  - [ ] `requirements.txt` güncelle: `python-docx`, `djangorestframework`, `django-filter`, `openai` (veya LLM client)
  - [ ] `settings.py` güncelle: `REST_FRAMEWORK` config, yeni app kayıtları
- [ ] **F0.3** Veritabanı yapılandırması
  - [ ] Development SQLite, Production PostgreSQL seçimi koru
  - [ ] İlk migration planını hazırla
- [ ] **F0.4** Statik dosyalar ve tema
  - [ ] NefOptik'in mevcut Bootstrap temasını refactor et
  - [ ] Sidebar menüyü yeni modüllere göre güncelle
  - [ ] Renk skalası CSS değişkenleri tanımla (risk skoru için)
- [ ] **F0.5** CI/CD ve test altyapısı
  - [ ] `pytest` + `pytest-django` kurulumu
  - [ ] Test dizin yapısı oluştur: `tests/unit/`, `tests/integration/`
  - [ ] GitHub Actions temel pipeline (lint + test)

---

## Faz 1 — Madde Havuzu Yönetimi (Çekirdek)

### 1.1 Havuz (ItemPool) CRUD
- [ ] **F1.1.1** Model: `ItemPool`
  - [ ] Alanlar: `name`, `course`, `semester`, `level` (Lisans1/2, YL), `tags`, `status` (ACTIVE/ARCHIVED), `owner`, `created_at`, `updated_at`
  - [ ] Migration oluştur ve çalıştır
- [ ] **F1.1.2** View: `ItemPoolListView`, `ItemPoolCreateView`, `ItemPoolUpdateView`, `ItemPoolArchiveView`
- [ ] **F1.1.3** Template: `pool_list.html`, `pool_form.html`, `pool_detail.html`
- [ ] **F1.1.4** URL tanımlamaları ve sidebar menü entegrasyonu
- [ ] **F1.1.5** Yetkilendirme: havuz sahibi + koordinatör erişimi
- [ ] **F1.1.6** Unit testler: CRUD operasyonları

### 1.2 Öğrenme Çıktısı (LearningOutcome) Yönetimi
- [ ] **F1.2.1** Model: `LearningOutcome`
  - [ ] Alanlar: `pool` (FK), `code`, `description`, `level` (Bloom taksonomisi), `weight` (opsiyonel), `order`, `is_active`
  - [ ] Migration
- [ ] **F1.2.2** Havuz detay sayfasında inline CRUD (HTMX/JS)
  - [ ] Ekleme, düzenleme, silme, sıralama
- [ ] **F1.2.3** API endpoint: `GET/POST /api/pools/{id}/outcomes/`
- [ ] **F1.2.4** Unit testler

### 1.3 Madde (Item) Modeli — Merkezi Yapı
- [ ] **F1.3.1** Model: `Item` (merkezi madde)
  - [ ] Alanlar: `stem` (madde kökü), `item_type` (MCQ/TF/MATCHING/OPEN), `difficulty_intended`, `author`, `created_at`, `updated_at`, `version`, `status` (DRAFT/ACTIVE/RETIRED)
- [ ] **F1.3.2** Model: `ItemChoice` (şıklar — MCQ için)
  - [ ] Alanlar: `item` (FK), `label` (A/B/C/D/E), `text`, `is_correct`, `order`
- [ ] **F1.3.3** Model: `ItemInstance` (havuz-madde ilişkisi)
  - [ ] Alanlar: `pool` (FK), `item` (FK), `learning_outcome` (FK, nullable), `is_fork` (kopyalandı mı?), `forked_from` (self FK), `added_at`, `added_by`
  - [ ] Unique constraint: `(pool, item)` — aynı havuzda aynı madde iki kez olamaz
- [ ] **F1.3.4** Migration ve indexler
- [ ] **F1.3.5** Unit testler: madde oluşturma, referanslama vs fork

### 1.4 Madde CRUD UI
- [ ] **F1.4.1** Madde oluşturma formu
  - [ ] Adım 1: Öğrenme çıktısı seçimi (dropdown — havuzun çıktılarından)
  - [ ] Adım 2: Madde kökü girişi
  - [ ] Adım 3: Şıklar girişi (dinamik form — JS ile şık ekleme/silme)
  - [ ] Adım 4: Doğru cevap işaretleme
- [ ] **F1.4.2** Madde listeleme (havuz detay sayfasında)
  - [ ] Filtreleme: öğrenme çıktısına göre, türe göre, duruma göre
  - [ ] Arama: madde kökünde metin arama
- [ ] **F1.4.3** Madde düzenleme ve silme (soft-delete)
- [ ] **F1.4.4** Madde detay sayfası: analiz sonuçları paneli (şimdilik boş, Faz 4'te doldurulacak)
- [ ] **F1.4.5** Sürüm geçmişi görüntüleme (basit audit trail)
- [ ] **F1.4.6** Unit ve integration testler

---

## Faz 2 — Word'den Toplu Madde Yükleme (Docx Import)

### 2.1 Docx Parser Servisi
- [ ] **F2.1.1** `python-docx` ile parse servisi: `services/import_docx.py`
  - [ ] Soru kökü + şık (A/B/C/D/E) + doğru cevap ayrıştırma
  - [ ] Hata toleransı: eksik şık → `manual_review=True`
  - [ ] Birden fazla soru formatı desteği (numaralı, yıldızlı vb.)
- [ ] **F2.1.2** Model: `DraftItem`
  - [ ] `pool` (FK), `stem`, `choices_json`, `correct_answer`, `manual_review` (bool), `review_note`, `import_batch` (FK), `status` (PENDING/APPROVED/REJECTED)
- [ ] **F2.1.3** Model: `ImportBatch`
  - [ ] `pool` (FK), `original_filename`, `uploaded_file`, `created_by`, `created_at`, `item_count`, `error_count`, `status`
- [ ] **F2.1.4** Unit testler (5 senaryo minimum)
  - [ ] Başarılı parse
  - [ ] Eksik şık
  - [ ] Eksik doğru cevap
  - [ ] Unicode karakterler
  - [ ] Çoklu soru aynı dosyada

### 2.2 Import Akışı UI
- [ ] **F2.2.1** Dosya yükleme sayfası: `import_upload.html`
  - [ ] Havuz seçimi (zorunlu) + dosya seçici
  - [ ] Dosya boyutu + uzantı güvenlik kontrolü (backend)
- [ ] **F2.2.2** Önizleme sayfası: `import_preview.html`
  - [ ] Taslak maddeler listesi (düzenlenebilir)
  - [ ] `manual_review` olanlar sarı işaretli
  - [ ] Tek tek düzenleme/reddetme imkanı
- [ ] **F2.2.3** Onay ve commit: taslakları gerçek `Item` + `ItemInstance` kayıtlarına dönüştürme
- [ ] **F2.2.4** DRF endpoints: `POST /api/import/upload/`, `GET /api/import/{batch}/preview/`, `POST /api/import/{batch}/commit/`

### 2.3 AI Destekli İyileştirmeler (Import Sırasında)
- [ ] **F2.3.1** LLM Client arayüzü: `services/llm_client.py`
  - [ ] Soyut `LLMClient` base class (provider değişebilir)
  - [ ] OpenAI implementasyonu (veya alternatif)
- [ ] **F2.3.2** Madde kökü/şık dil temizliği önerisi
- [ ] **F2.3.3** Öğrenme çıktısı önerisi (import sırasında toplu)
- [ ] **F2.3.4** AI önerilerinin `DraftItem`'a eklenmesi ve UI'da gösterimi

---

## Faz 3 — AI Öğrenme Çıktısı Eşleme

### 3.1 Öneri Motoru
- [ ] **F3.1.1** Model: `OutcomeSuggestion`
  - [ ] `item` (FK), `learning_outcome` (FK), `score` (0-1), `reasoning`, `status` (PENDING/ACCEPTED/REJECTED), `created_at`
- [ ] **F3.1.2** Servis: `services/outcome_suggestion.py`
  - [ ] `suggest_outcomes(item_text, outcomes_list)` → top 1-3 eşleşme + skor + gerekçe
  - [ ] LLMClient kullanarak eşleme
  - [ ] Anahtar kelime/tema bazlı gerekçe üretimi
- [ ] **F3.1.3** DRF endpoints
  - [ ] `GET /api/items/{id}/outcome-suggestions/` → önerileri al
  - [ ] `POST /api/items/{id}/assign-outcome/` → kullanıcı onayı ile ata

### 3.2 UI Entegrasyonu
- [ ] **F3.2.1** Madde detay sayfasında "AI Öneri" paneli
  - [ ] Öneriler liste halinde (skor + gerekçe gösterilir)
  - [ ] Kullanıcı seçip "Onayla" der
  - [ ] Audit trail: öneri kaydı saklanır (kim ne zaman onayladı)
- [ ] **F3.2.2** Toplu öneri: havuz bazında tüm maddelere AI önerisi çalıştır

---

## Faz 4 — Madde Analizi ve Görünürlük

### 4.1 Analiz Sonuç Modelleri
- [ ] **F4.1.1** Model: `ItemAnalysisResult`
  - [ ] `item_instance` (FK), `test_form` (FK), `difficulty_p` (0-1), `discrimination_r` (-1..1), `distractor_efficiency` (0-1), `flagged` (bool), `risk_score` (0-100), `analysis_data_json`, `created_at`
- [ ] **F4.1.2** NefOptik'in `StatisticsService`'ini genişlet: `item_analysis_service.py`
  - [ ] Mevcut `_calculate_item_analysis()` → zorluk, ayırt edicilik hesapları
  - [ ] Çeldirici verimliliği hesaplama
  - [ ] Risk skoru hesaplama fonksiyonu
- [ ] **F4.1.3** Unit testler: risk_score(), metrik hesapları

### 4.2 Risk Skoru ve Renk Skalası
- [ ] **F4.2.1** `risk_score()` fonksiyonu
  - [ ] Girdi: `difficulty_p`, `discrimination_r`, `distractor_efficiency`
  - [ ] Çıktı: 0-100 skor
  - [ ] Sınıflar: 0-30 kırmızı, 31-60 sarı, 61-100 yeşil
- [ ] **F4.2.2** CSS renk skalası: `.risk-red`, `.risk-yellow`, `.risk-green` + gradient badge
- [ ] **F4.2.3** Madde listesinde renk etiketi gösterimi

### 4.3 Uygulama Sonrası Analizler Paneli
- [ ] **F4.3.1** API: `GET /api/forms/{id}/analysis-summary/`
  - [ ] Ortalama zorluk, problemli madde sayısı, genel güvenirlik
- [ ] **F4.3.2** API: `GET /api/items/?pool_id=...` → risk_score dahil
- [ ] **F4.3.3** UI: "Uygulama Sonrası Analizler" dashboard sayfası
  - [ ] Form bazında özet kartlar
  - [ ] Madde bazında detay tablosu (renkli)
  - [ ] Grafikler (matplotlib/chart.js): zorluk dağılımı, ayırt edicilik dağılımı

---

## Faz 5 — Test Formu Oluşturma (Blueprint + Belirtke Tablosu)

### 5.1 Form Modelleri
- [ ] **F5.1.1** Model: `TestForm`
  - [ ] `pool` (FK, zorunlu), `name`, `description`, `created_by`, `created_at`, `status` (DRAFT/ACTIVE/APPLIED/ARCHIVED), `generation_rule`
- [ ] **F5.1.2** Model: `FormItem`
  - [ ] `form` (FK), `item_instance` (FK), `order`, `points`
- [ ] **F5.1.3** Model: `Blueprint`
  - [ ] `name`, `pool` (FK), `source_form` (FK, nullable), `outcome_distribution_json`, `total_items`, `created_by`
- [ ] **F5.1.4** Model: `SpecificationTable` (Belirtke Tablosu)
  - [ ] `pool` (FK), `name`, `rows_json` (öğrenme çıktısı × konu matris), `created_by`
- [ ] **F5.1.5** Model: `FormGenerationRule`
  - [ ] `use_blueprint` (FK, nullable), `use_specification_table` (FK, nullable), `exclude_improved_forms` (bool), `excluded_forms` (M2M TestForm)
- [ ] **F5.1.6** Migration ve indexler

### 5.2 Form Oluşturma Sihirbazı (Wizard UI)
- [ ] **F5.2.1** Adım 1: Havuz seçimi (zorunlu)
- [ ] **F5.2.2** Adım 2: Ayarlar
  - [ ] Belirtke tablosu kullan checkbox + seçici
  - [ ] Blueprint seç (önceki formlardan) veya yeni dağılım
  - [ ] "Geliştirilmiş formlardaki maddelerin dışında" checkbox
- [ ] **F5.2.3** Adım 3: Madde seçimi
  - [ ] Otomatik doldur (blueprint/belirtke'ye göre)
  - [ ] Manuel seçim/ekleme/çıkarma
  - [ ] Dışlanan maddelerin görüntülenmesi
- [ ] **F5.2.4** Adım 4: Önizleme + kaydet (tek adım — atomik transaction)
- [ ] **F5.2.5** Backend: `FormCreateService` (atomik transaction)

### 5.3 Form CRUD ve Listeleme
- [ ] **F5.3.1** Form listesi (havuz bazında)
- [ ] **F5.3.2** Form detay: madde listesi, istatistikler
- [ ] **F5.3.3** Form düzenleme (madde ekleme/çıkarma)
- [ ] **F5.3.4** Blueprint kopyalama/klonlama
- [ ] **F5.3.5** Unit ve integration testler

---

## Faz 6 — Test ve Madde Analizi Entegrasyonu

### 6.1 Veri Okuma Akışı
- [ ] **F6.1.1** NefOptik parser'ını koru ve genişlet
  - [ ] Mevcut `ConfigurableParser` + `ParsingService` aynen kalacak
  - [ ] Yeni akış: önce havuz → sonra form seçimi ile ilişkilendirme
- [ ] **F6.1.2** View: `AnalysisDataUploadView`
  - [ ] Havuz seçimi (1. adım)
  - [ ] Form seçimi (2. adım, opsiyonel: yeni form oluştur)
- [ ] **F6.1.3** Yanıt anahtarı eşleme
  - [ ] Formun maddeleri ile optik okuyucu soru sırası eşleştirilecek
  - [ ] Eşleşme uyumsuzluğu uyarıları

### 6.2 Analiz Sonuçlarını DB'ye Aktarma
- [ ] **F6.2.1** Maddeler bazında istatistik hesaplama
  - [ ] NefOptik `StatisticsService._calculate_item_analysis()` kullanılacak
  - [ ] Her madde için `ItemAnalysisResult` kaydı oluşturulacak
- [ ] **F6.2.2** "Analizi DB'ye Aktar" butonu ve akışı
- [ ] **F6.2.3** Analiz geçmişi: aynı maddenin farklı uygulamalardaki sonuçları

### 6.3 Entegre Görünümler
- [ ] **F6.3.1** Test Formları menüsü altında "Test ve Madde Analizi" alt menüsü
- [ ] **F6.3.2** Madde detay sayfasında analiz geçmişi gösterimi
- [ ] **F6.3.3** Form detay sayfasında toplu analiz özeti
- [ ] **F6.3.4** Unit ve integration testler

---

## Faz 7 — Yetkilendirme ve Kullanıcı Yönetimi

- [ ] **F7.1** NefOptik'in mevcut kullanıcı modelini genişlet
  - [ ] Roller: `INSTRUCTOR`, `COORDINATOR`, `ASSISTANT`, `ADMIN`
  - [ ] `UserProfile` → `role` alanı ekle
- [ ] **F7.2** Havuz bazlı erişim kontrolü
  - [ ] `PoolPermission` modeli: `user`, `pool`, `permission_level`
  - [ ] Mixin: `PoolAccessMixin`
- [ ] **F7.3** Ders/dönem bazlı yetki filtreleme
- [ ] **F7.4** Admin dashboard genişletme: havuz istatistikleri, kullanıcı aktivitesi
- [ ] **F7.5** Unit testler: yetki kontrolleri

---

## Faz 8 — Fonksiyonel Olmayan Gereksinimler

- [ ] **F8.1** İzlenebilirlik (Audit Trail)
  - [ ] `ItemAuditLog` modeli: `item`, `action`, `user`, `timestamp`, `details_json`
  - [ ] Her madde düzenlemesinde log kaydı
  - [ ] Hangi formda kullanıldı bilgisi
- [ ] **F8.2** Performans
  - [ ] Word import ve analiz sonuçları için pagination
  - [ ] Madde listesi için DB index optimizasyonu
  - [ ] Büyük havuzlar için select_related/prefetch_related
- [ ] **F8.3** Güvenlik
  - [ ] Dosya yükleme: boyut limiti, uzantı kontrolü, MIME check
  - [ ] CSRF, XSS korumaları (Django default + ek kontroller)
  - [ ] API rate limiting
- [ ] **F8.4** Denetlenebilirlik
  - [ ] Analiz değerlerinin hangi veri setinden üretildiği tracing
  - [ ] Import batch → madde → analiz kaydı ilişki zinciri

---

## Faz 9 — Son Kontroller ve Deployment

- [ ] **F9.1** Tüm testlerin çalıştığını doğrula
- [ ] **F9.2** README.md güncelle
- [ ] **F9.3** Deployment konfigürasyonu
  - [ ] Production settings
  - [ ] Docker Compose (opsiyonel)
  - [ ] Static files collection
- [ ] **F9.4** Kullanıcı kılavuzu / yardım sayfası
- [ ] **F9.5** Son kullanıcı testi ve geri bildirim

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
