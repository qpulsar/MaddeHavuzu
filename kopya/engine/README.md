# Kopya Analizi Hesaplama Motoru

Çoktan seçmeli sınav yanıt örüntülerinden **istatistiksel kopya göstergeleri** hesaplar. Karar destek amaçlıdır: kopya kararı vermez, inceleme önceliği ve gösterge üretir. Web arayüzü `kopya/` uygulamasındadır; bu klasör yalnızca hesaplamayı içerir ve istatistikleri değiştirilmemelidir.

Kaynak: `cheating` FastAPI modülü. Araştırma betikleri (simülasyon, R karşılaştırma, demo veri üretimi, sonuç paketi) buraya alınmadı; buradaki sayılar o çalışmanın özetidir.

## Dosyalar

| Dosya | İçerik |
|---|---|
| `core.py` | `ExamData`, `IndexValue`, `PairResult`, kanonik uzaya dönüşüm, girdi doğrulama |
| `_pairwise.py` | `analyze_exam()`: tüm yönlü çiftler, BH-FDR, `AnalysisResult` |
| `_formulas.py` | K, K\*, K1, K2 (Holland 1996), S1, S2 (Sotaridona & Meijer 2002, 2003) |
| `_person_fit.py` | U3 (van der Flier 1982), Hᵀ (Sijtsma & Meijer 1992) |
| `_descriptive.py` | Ortak doğru/yanlış/boş, uyum oranı, en uzun ortak yanlış bloğu |
| `_neighbor.py` | Oturma kodu ayrıştırma, Moore komşuluğu, oturma raporu |
| `excel_upload.py` | Excel dosyasını doğrulayıp `ExamData`'ya çevirir |
| `power_lookup.py` + `summary_tables.json` | Sınava özgü K1 duyarlılık (güç) göstergesi |

## Kullanım

```python
from kopya.engine import analyze_exam
result = analyze_exam(data, alpha=0.01, subgroup_exclusion="source_only")
```

`data` bir `ExamData`dır. Yanıtlar pozisyon uzayındadır (1..K seçenek, 0 boş, −1 çoklu/okunamaz); `permutation[kitapçık, pozisyon]` kanonik madde indeksini verir. Optik Okuma batch'leri `kopya/adapter.py` ile, Excel yüklemeleri `excel_upload.read_excel()` ile dönüştürülür.

## Kalibrasyon

K1, K2, S1 ve S2, R `CopyDetect 1.3` referansıyla `form2[1:500, 1:10]` verisinde, `(e200287, e200169)` çifti için **birebir** eşleşti (fark < 1e-6):

| İndeks | R | Python |
|---|---|---|
| K1 | 0.1276175 | 0.1276175 |
| K2 | 0.1072546 | 0.1072546 |
| S1 | 0.1012689 | 0.1012689 |
| S2 | 0.3115374 | 0.3115374 |

U3 ve Hᵀ bağımsız olarak doğrulanamadı; bu yüzden `DESCRIPTIVE_ONLY` olarak raporlanır. K (empirik) küçük alt gruplarda α kontrolü sağlayamadığı için de betimseldir.

Simülasyon bulguları (36 hücre × 1000 tekrar):
- Null altında empirik α = .0002–.0028; nominal .01'in altında, yani indeksler muhafazakâr.
- Küçük n'de indeksler çökmüyor: K1 gücü n=20'de 0.454, n=200'de 0.542 (k=40, kopya oranı %40).
- Öğrenci sayısı eşiği yoktur. Hesaplanamayan çiftler gerekçesiyle `NOT_COMPUTABLE` olur (ör. kaynak öğrencinin hiç yanlışı yoksa; S1/S2'de loglineer uyum G² p < .01 ise).

## Raporlama kuralları

- **BH-FDR öğrenci ikilisi başına:** A→B ve B→A aynı ikilinin iki okumasıdır. BH'ye min(p) ile tek test olarak girer; test sayısı n(n−1)/2'dir.
- **Oturma filtresi:** Oturma kodu kapsamı ≥ %80 ise yalnız Moore komşusu çiftler (aynı salon, satır ve koltuk farkı ≤ 1) birincil katmana alınır ve p-değeri + FDR alır. Komşu olmayanlar ikincil katmanda yalnız sıralanır (FDR yok, karar iddiası yok). Oturma kodu olmayan veya çakışan öğrencilerin çiftleri muhafazakâr olarak birincil katmanda kalır. Filtrenin güce etkisi simülasyonda ölçülmedi.
- **Küçük sınıfta FDR sıkıdır:** Doğru tespit edilen kopya bile düzeltilmiş eşiği geçmeyebilir. Bu bir hata değil, yöntemin sınırıdır. Bu yüzden arayüz iki çıktı verir: FDR'yi geçen ikililer (bilimsel iddia) ve 5 indeksin ham p minimumuna göre "En Şüpheli N Çift" (inceleme önceliği, karar iddiası yok).
- **Şans referansı:** Liste kopya olmayan sınıfta da dolar. Panelde gözlenen en düşük p, bağımsız ve uniform testler için beklenen minimumla (≈ 1/(m+1)) kıyaslanır. İki varsayım da tam sağlanmaz (indeksler muhafazakâr, aynı öğrenciyi paylaşan çiftler bağımlı); referans kaba bir büyüklük mertebesidir.

## Bilinen belirsizlikler

1. "Yanlış": geçerli işaret ve anahtardan farklı (boş yanlış sayılmaz).
2. `_delta_weight` (S2) Sotaridona 2003 Eşitlik 13'e sadıktır; δ, P=1'de 0 değil ~0.328'dir.
3. `M*` yuvarlaması `round` (Sotaridona 2003 s. 14).
4. İkili puanlamada boş/çoklu = 0 (muhafazakâr).
5. Seçenek karıştırma (kitapçıklar arası farklı harf) desteklenmez.

## Referanslar

- Holland (1996). ETS RR-96-97
- Sotaridona & Meijer (2002). *J. Educ. Meas.* 39(2), 115-132
- Sotaridona & Meijer (2003). *J. Educ. Meas.* 40, 53-69
- van der Flier (1982). *J. Cross-Cultural Psych.*
- Sijtsma & Meijer (1992). *Appl. Psych. Meas.* 16, 149-157
- Meijer & Sijtsma (2001). *Appl. Psych. Meas.* 25, 107-135
- Zopluoglu (2012). *Appl. Psych. Meas.* 37, 93-95
