# Staj-2 model karşılaştırması

Bu klasör, Staj-2 defterinin 5. ve 6. günlerinde (10–11.08.2026) yapılan
eşik yöntemi, Random Forest ve SVM karşılaştırmasının kodlarını ve kullanılan
özellik tablosunu içerir. Canlı uygulama bu dosyaları çağırmaz.

Canlı ortamda kumaşın rengi ve dokusu bütün lazer profilini birlikte
kaydırdığı için bu sınıflandırıcılar ürüne alınmadı. Kabarıklık kararı daha
sonra yerel lazer çizgisi bozulmasına dayanan kurala taşındı
(`src/laser_detection.py`).

## İçerik

| Dosya | Açıklama |
| --- | --- |
| `veri/wp7_ozellikler.csv` | 126 lazer açık/kapalı görüntü çiftinden çıkarılan sayısal özellikler |
| `WP7_random_forest_ogrenci.py` | Random Forest eğitimi, test sonucu ve özellik önemleri |
| `WP7_svm_ogrenci.py` | StandardScaler + RBF SVM, C/gamma seçimi ve test sonucu |
| `test_model_karsilastirma.py` | Veri bölmesini ve defterdeki sonuçları kontrol eder |

## Veri

- Hedef: `0 = normal yüzey (D00)`, `1 = geometrik kusur (D01–D05)`.
- Her satır bir lazer açık/kapalı çiftidir. Özellikler, aynı kumaşın üç düz
  (D00) çekiminin medyan profiline göre hesaplanmıştır.
- Bölme kumaş bazındadır; aynı kumaşın tekrarları farklı gruplara düşmez:

| Grup | Kumaşlar | Çift |
| --- | --- | ---: |
| Eğitim | K001, K004, K006, K007, K009 | 90 |
| Doğrulama | K003 | 18 |
| Test | K011 | 18 |

Her kumaşta 3 normal ve 15 kusurlu çift vardır. Sınıflar dengesiz olduğu için
modellerde `class_weight="balanced"` kullanılır ve dengeli doğruluk raporlanır.

## Kullanılan özellikler

`sapma_p95_gurultu_orani`, `sapma_std_px`, `sapma_medyan_px`, `sapma_p90_px`,
`aktif_oran_0_5px`.

## Sonuçlar (K011 bağımsız testi)

| Yöntem | Ayar | Doğru | TN / FP / FN / TP | F1 | Dengeli doğruluk |
| --- | --- | ---: | --- | ---: | ---: |
| Eşik | `sapma_std_px >= 0.431129` | 16/18 | 2 / 1 / 1 / 14 | %93,33 | %80,00 |
| Random Forest | 400 ağaç, `min_samples_leaf=4`, `max_features=0.7` | 18/18 | 3 / 0 / 0 / 15 | %100 | %100 |
| SVM (RBF) | `C=0.1`, `gamma="scale"` | 16/18 | 2 / 1 / 1 / 14 | %93,33 | %80,00 |

Random Forest özellik önemleri: `sapma_p95_gurultu_orani` %52,98,
`sapma_std_px` %17,97, `sapma_medyan_px` %15,02, `sapma_p90_px` %8,58,
`aktif_oran_0_5px` %5,45.

Test seti tek bir kumaştan ve yalnızca üç normal örnekten oluşur. Bu nedenle
%100 sonucu genel başarı kanıtı değil, ilk karşılaştırma sonucudur.

## Çalıştırma

Proje kökünde, sanal ortam etkinken:

```powershell
python -m pip install scikit-learn==1.7.2
python staj2_deneyleri/WP7_random_forest_ogrenci.py
python staj2_deneyleri/WP7_svm_ogrenci.py
python -m unittest discover -s staj2_deneyleri -p "test_*.py" -v
```

Eğitilen modeller `output/staj2/` altına `.joblib` olarak kaydedilir.
`output/` Git dışında tutulur.
