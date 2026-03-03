# Madde Havuzu ve Test Sistemi — Proje Bağlamı ve Özellik Takibi

> **Son güncelleme:** 2026-03-03
> **Amaç:** Bu dosya, projenin bağlamını, özelliklerini ve geliştirme sırasında alınan kararları takip eder.

---

## 1. Proje Özeti

**Madde Havuzu ve Test Sistemi**, üniversitelerde sınav hazırlama sürecini uçtan uca yönetmeyi amaçlayan bir Django web uygulamasıdır.

### Temel Sorunlar (Çözülen)
1. **Dağınık madde üretimi** → Merkezi madde havuzu + Word'den toplu yükleme
2. **Zayıf öğrenme çıktısı bağı** → Havuz bazlı çıktı listeleri + AI destekli eşleme
3. **Hatalı test formu süreci** → Tek adımlı havuz-bazlı form oluşturma + blueprint/belirtke
4. **Görünür olmayan analiz** → Renk skalası ile risk göstergeli madde paneli
5. **Kopuk analiz entegrasyonu** → Havuz→Form→Veri→Analiz→DB zinciri

### Hedef Kullanıcılar
| Rol | Temel İşlemler |
|-----|---------------|
| **Öğretim elemanı** | Havuz oluştur, madde üret/aktar, form oluştur, analizi yorumla |
| **Koordinatör** | Kazanım standardize, blueprint şablon, kalite takibi |
| **Asistan/Operatör** | Word import, optik veri okuma, eşleştirme |
| **Sistem yöneticisi** | Yetki yönetimi, ders/dönem yaşam döngüsü |

---

## 2. Referans Proje: NefOptik

### 2.1 Genel Bilgiler
- **GitHub:** `qpulsar/nefoptik`
- **Stack:** Django 4.2+ / PostgreSQL (dev: SQLite) / Bootstrap / openpyxl
- **Klonlanan konum:** `nefoptik_ref/`

### 2.2 Devralınan Modüller
| Modül | Dosya | Amaç | Durumu |
|-------|-------|------|--------|
| Kullanıcı yönetimi | `models/user_profile.py` | Kayıt + admin onayı | Genişletilecek (+role) |
| Dosya formatı | `models/file_format.py` | Optik okuyucu format tanımı | Aynen korunacak |
| Yükleme/sonuç | `models/upload.py` | UploadSession, StudentResult | Genişletilecek (+form FK) |
| Dosya parse | `parsers/configurable.py` | TXT ayrıştırma | Aynen korunacak |
| Puanlama | `services/grading.py` | Doğru/yanlış/boş hesaplama | Aynen korunacak |
| İstatistik | `services/statistics.py` | KR-20, Cronbach α, madde analizi | Genişletilecek |
| Kopya analizi | `services/analysis.py` | Benzerlik skoru | Aynen korunacak |
| Excel export | `services/export_xlsx.py` | Formatlı xlsx indirme | Genişletilecek |

### 2.3 Silinecek/Dönüştürülecek Modüller
- Yok — tüm mevcut modüller korunacak veya genişletilecek.
- Yeni `itempool` app'i eklenecek.

---

## 3. Özellik Listesi ve Durum Takibi

### Faz 0: Altyapı
| Özellik | Durum | Not |
|---------|-------|-----|
| Proje iskeleti | 🔴 Başlanmadı | Fork + refactor |
| requirements.txt | 🔴 Başlanmadı | python-docx, DRF, openai eklenmeli |
| Yeni app: itempool | 🔴 Başlanmadı | |
| Test altyapısı | 🔴 Başlanmadı | pytest + pytest-django |

### Faz 1: Madde Havuzu Çekirdek
| Özellik | Durum | Not |
|---------|-------|-----|
| ItemPool CRUD | 🔴 Başlanmadı | |
| LearningOutcome CRUD | 🔴 Başlanmadı | Havuz detayında inline |
| Item + ItemChoice model | 🔴 Başlanmadı | |
| ItemInstance (referans/fork) | 🔴 Başlanmadı | Kritik tasarım kararı |
| Madde oluşturma formu | 🔴 Başlanmadı | ÖÇ seçimi → kök → şıklar |
| Madde listeleme/arama | 🔴 Başlanmadı | |

### Faz 2: Word Import
| Özellik | Durum | Not |
|---------|-------|-----|
| Docx parser servisi | 🔴 Başlanmadı | python-docx |
| DraftItem / ImportBatch model | 🔴 Başlanmadı | |
| Dosya yükleme UI | 🔴 Başlanmadı | |
| Önizleme & düzenleme UI | 🔴 Başlanmadı | |
| Commit (taslak → gerçek) | 🔴 Başlanmadı | |

### Faz 3: AI Eşleme
| Özellik | Durum | Not |
|---------|-------|-----|
| LLMClient arayüzü | 🔴 Başlanmadı | Soyut base class |
| OutcomeSuggestion model | 🔴 Başlanmadı | |
| Öneri servisi | 🔴 Başlanmadı | |
| AI paneli UI | 🔴 Başlanmadı | |

### Faz 4: Madde Analizi
| Özellik | Durum | Not |
|---------|-------|-----|
| ItemAnalysisResult model | 🔴 Başlanmadı | |
| risk_score() fonksiyonu | 🔴 Başlanmadı | 0-30🔴 31-60🟡 61-100🟢 |
| Renk skalası CSS | 🔴 Başlanmadı | |
| Analiz dashboard | 🔴 Başlanmadı | |

### Faz 5: Test Formu
| Özellik | Durum | Not |
|---------|-------|-----|
| TestForm/FormItem model | 🔴 Başlanmadı | |
| Blueprint model | 🔴 Başlanmadı | |
| SpecificationTable model | 🔴 Başlanmadı | |
| Form wizard UI | 🔴 Başlanmadı | 4 adımlı sihirbaz |
| "Dışarıda bırak" filtresi | 🔴 Başlanmadı | Geliştirilmiş form maddeleri |

### Faz 6: Analiz Entegrasyonu
| Özellik | Durum | Not |
|---------|-------|-----|
| Havuz→Form ilişkilendirme | 🔴 Başlanmadı | |
| Yanıt anahtarı eşleme | 🔴 Başlanmadı | |
| Analizi DB'ye aktarma | 🔴 Başlanmadı | |
| Madde yanında analiz göst. | 🔴 Başlanmadı | |

---

## 4. Tasarım Kararları Günlüğü

### Karar 1: Item + ItemInstance Yaklaşımı
- **Tarih:** 2026-03-03
- **Karar:** Merkezi `Item` tablosu + havuz içi `ItemInstance` (referans) yaklaşımı
- **Gerekçe:** Aynı madde birden fazla havuzda kullanılabilir; havuz bazında düzenleme gerekiyorsa "fork" mekanizması ile kopya oluşturulur
- **Alternatif:** Sadece `Item` + M2M → reddedildi çünkü havuz bazlı öğrenme çıktısı ataması yapılamaz

### Karar 2: Tek Adımlı Form Kaydı
- **Tarih:** 2026-03-03
- **Karar:** Form oluşturma atomik transaction ile tek adımda tamamlanacak
- **Gerekçe:** NefOptik'teki iki aşamalı kayıt bug'ı tekrarlanmamalı
- **Uygulama:** Django `transaction.atomic()` kullanılacak

### Karar 3: AI Önerileri = Sadece Öneri
- **Tarih:** 2026-03-03
- **Karar:** AI eşleme sonuçları otomatik kaydedilmeyecek, kullanıcı onayı zorunlu
- **Gerekçe:** Hatalı eşleme riski; kullanıcı güveni; denetlenebilirlik
- **Uygulama:** `OutcomeSuggestion` tablosunda PENDING → ACCEPTED/REJECTED flow

### Karar 4: Proje Adı Refactor
- **Tarih:** 2026-03-03
- **Karar:** `optikform` proje adı → `maddehavuzu` olarak değiştirilecek
- **Gerekçe:** Yeni projenin amacı madde havuzu yönetimi; optik okuma sadece bir alt modül

---

## 5. MCP ve Araç Kullanımı

### Mevcut ve Kullanılabilir
| Araç | Durum | Kullanım |
|------|-------|----------|
| `sequential-thinking` MCP | ✅ Yüklü | Karmaşık tasarım kararları için |
| Dosya araçları (view, edit, search) | ✅ Yerleşik | Kod geliştirme |
| Terminal araçları (run_command) | ✅ Yerleşik | Django komutları |
| Browser araçları | ✅ Yerleşik | UI testi |

### Eksik — Kullanıcının Yüklemesi Gereken
| Araç | Amaç | Öncelik |
|------|-------|---------|
| `github` MCP | Fork, PR, issue yönetimi | 🔵 Orta |
| `postgres` MCP | DB sorguları, migration kontrolü | 🟡 Düşük |
| Django skill | Django best practices, boilerplate | 🟡 Düşük |
| Python skill | Genel Python patterns | 🟡 Düşük |

---

## 6. Bağımlılıklar (requirements.txt — Planlanan)

```
# NefOptik mevcut
Django>=4.2,<5.0
psycopg2-binary>=2.9
openpyxl>=3.1
python-dotenv>=1.0

# Yeni eklenenler
djangorestframework>=3.14
django-filter>=23.0
python-docx>=1.0
openai>=1.0          # AI öğrenme çıktısı eşleme (opsiyonel)
pytest>=7.0
pytest-django>=4.5
```

---

## 7. Sık Kullanılan Komutlar (Geliştirme)

```bash
# Sunucu başlat
python manage.py runserver

# Migration oluştur
python manage.py makemigrations itempool

# Migration uygula
python manage.py migrate

# Test çalıştır
pytest

# Super user oluştur
python manage.py createsuperuser

# Static dosyaları topla
python manage.py collectstatic
```

---

## 8. Açık Sorular

1. ~~Aynı madde iki havuzda kullanılabilir mi?~~ → ✅ Evet, Item+ItemInstance yaklaşımı ile
2. AI provider: OpenAI mi, yerel model mi? → ❓ Kullanıcıya sorulacak
3. Frontend framework: HTMX mı, tamamen Vanilla JS mi? → ❓ Belirlenmeli
4. Deployment hedefi: Docker mu, bare metal mi? → ❓ Kullanıcıya sorulacak
