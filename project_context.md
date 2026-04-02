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

> **Not:** Faz 0–13 tamamlanmıştır. Ayrıntılı görev takibi için `tasklist.md` dosyasına bakın.

### Tamamlanan Fazlar (Özet)
| Faz | Özellik | Durum |
|-----|---------|-------|
| Faz 0 | Proje iskeleti, altyapı, CI/CD | ✅ Tamamlandı |
| Faz 1 | ItemPool, LearningOutcome, Item, ItemChoice, ItemInstance CRUD | ✅ Tamamlandı |
| Faz 2 | Word (.docx) import, DraftItem, ImportBatch | ✅ Tamamlandı |
| Faz 3 | AI öğrenme çıktısı eşleme (GeminiClient), OutcomeSuggestion | ✅ Tamamlandı |
| Faz 4 | ItemAnalysisResult, risk_score(), renk skalası, analiz dashboard | ✅ Tamamlandı |
| Faz 5 | TestForm, FormItem, Blueprint, SpecificationTable, form wizard | ✅ Tamamlandı |
| Faz 6 | Optik veri entegrasyonu, yanıt anahtarı, analiz DB aktarımı | ✅ Tamamlandı |
| Faz 7 | Yetkilendirme, PoolPermission, rol bazlı erişim | ✅ Tamamlandı |
| Faz 8 | Audit trail, performans, güvenlik | ✅ Tamamlandı |
| Faz 9 | Deployment konfigürasyonu | ✅ Tamamlandı |
| Faz 10 | SHORT_ANSWER tipi, max_choices, dinamik şık UI | ✅ Tamamlandı |
| Faz 11 | StudentGroup, ExamApplication, soru tekrar önleme | ✅ Tamamlandı |
| Faz 12 | ExamTemplate, WeasyPrint PDF üretimi, sınav kağıdı | ✅ Tamamlandı |
| Faz 13 | TestForm↔UploadSession bağlantısı, öğrenme çıktısı başarı raporu | ✅ Tamamlandı |

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
google-generativeai  # AI öğrenme çıktısı eşleme — GeminiClient (GEMINI_API_KEY env)
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
