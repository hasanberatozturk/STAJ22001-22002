# Kod rehberi: staj günü → dosya → satır aralığı

Bu rehber, staj defterlerinde anlatılan çalışmaların koddaki karşılığını gösterir.
Defterde ekran görüntüsü olarak yer almayan kodlar için dosya ve satır aralığı
verilmiştir. Satır numaraları bu depodaki dosyalara aittir.

## Klasörler

| Klasör | İçerik |
| --- | --- |
| `staj1_deneyleri/` | Staj-1: kamera kalibrasyonu, lazer pozlama ve yerel yükselti deneyleri |
| `staj2_deneyleri/` | Staj-2: eşik, Random Forest ve SVM karşılaştırması (5 özellikli sürüm) |
| `staj2_deneyleri/wp8_raspberry_pi/` | Staj-2: Raspberry Pi canlı tahmin, yeniden eğitim, optik doğrulama ve çizgi sapma (R3) kodları |
| `staj2_deneyleri/wp9_birlesik_arayuz/` | Staj-2: Raspberry Pi dokunmatik birleşik arayüz ve R4 kabarıklık modülü |
| `src/`, `app.py` | Staj-2 sonu: Windows masaüstü uygulaması (telefon/USB kamera) |
| `tests/` | Masaüstü uygulamasının testleri |

`wp8_raspberry_pi/` ve `wp9_birlesik_arayuz/` klasörleri Raspberry Pi'de çalışan
özgün betiklerin arşividir. Model dosyaları (`.joblib`, `.pt`) ve ham görüntüler
depoya eklenmemiştir. Betikler Pi'deki klasör yollarını (`~/WP8_CANLI`,
`~/WP8_FINAL`, `~/WP9_KAYITLAR`) bekler.

---

## Staj-1

| Gün | Konu | Dosya | Satır |
| --- | --- | --- | --- |
| 11 | Desen köşelerinin gerçek konumları (mm) | `staj1_deneyleri/kamera_kalibrasyon_v2.py` | 19–28 |
| 11 | Köşe bulma (SB yöntemi, yedek klasik yöntem + alt piksel) | `staj1_deneyleri/kamera_kalibrasyon_v2.py` | 31–65 |
| 11 | `cv2.calibrateCamera` | `staj1_deneyleri/kamera_kalibrasyon_v2.py` | 189–197 |
| 11 | RMS hatasının elle hesabı (`projectPoints`, görüntü başına RMSE) | `staj1_deneyleri/kamera_kalibrasyon_v2.py` | 209–230 |
| 12 | Distorsiyon düzeltme (`getOptimalNewCameraMatrix`, alpha = 0, `undistort`) | `staj1_deneyleri/kamera_kalibrasyon_v2.py` | 250–283 |
| 19 | Pozlama taraması (1000–20000 µs, lazer açık/kapalı) | `staj1_deneyleri/lazer_pozlama_taramasi.sh` | 20–43 |
| 20 | Lazer çekim ayarları (2500 µs, gain 1, sabit AWB, manuel odak) | `staj1_deneyleri/yerel_yukselti_cekimi.sh` | 21–32 |
| 20 | Lazer açık − kapalı, kırmızı skor, alt piksel çizgi merkezi | `staj1_deneyleri/yerel_yukselti_analizi.py` | 17–39 |
| 20 | Düz/yükselti medyanı, doğru uydurup genel eğimi çıkarma, yerel kayma | `staj1_deneyleri/yerel_yukselti_analizi.py` | 62–84 |
| – | Sentetik görüntüyle algoritma testi (bilinen 10 px kayma) | `staj1_deneyleri/test_deneyler.py` | 29–39, 63–74 |

## Staj-2

### Lazer kanalı: veri seti ve model karşılaştırması (Gün 1–7)

| Gün | Konu | Dosya | Satır |
| --- | --- | --- | --- |
| 1–2 | Lazer açık − kapalı farkı ve kırmızı skor (defter Şekil 1) | `src/laser_detection.py` | 91–100 |
| 2 | Çizgi merkezinin ağırlıklı ortalamayla bulunması | `src/laser_detection.py` | 158–178 |
| 3 | Çizgi uzunluğu/doluluğu ve kalite puanı | `src/laser_detection.py` | 200–225 |
| 4 | Kumaş bazında bölmenin okunması | `staj2_deneyleri/WP7_random_forest_ogrenci.py` | 45–72 |
| 4 | Bölmenin kumaş bazında olduğunun testi (90 / 18 / 18) | `staj2_deneyleri/test_model_karsilastirma.py` | 36–49 |
| 5 | Eşik yöntemi (`sapma_std_px ≥ 0,431129`) | `staj2_deneyleri/test_model_karsilastirma.py` | 51–57 |
| 6 | Random Forest (400 ağaç, dengeli sınıf ağırlığı) | `staj2_deneyleri/WP7_random_forest_ogrenci.py` | 75–86 |
| 6 | Metrikler ve özellik önemleri | `staj2_deneyleri/WP7_random_forest_ogrenci.py` | 97–132 |
| 7 | SVM pipeline (StandardScaler + RBF) | `staj2_deneyleri/WP7_svm_ogrenci.py` | 73–91 |
| 7 | C ve gamma seçimi (yalnızca doğrulama kumaşında) | `staj2_deneyleri/WP7_svm_ogrenci.py` | 44–45, 137–167 |

### Raspberry Pi canlı sistem (Gün 8–13) – `staj2_deneyleri/wp8_raspberry_pi/`

| Gün | Konu | Dosya | Satır |
| --- | --- | --- | --- |
| 8 | Kayıtlı K011 verisiyle Pi'de model yükleme testi | `WP8_offline_tahmin.py` | 149–204 |
| 8 | Özellik sırasının modelle eşleştirilmesi | `WP8_canli_tahmin_onceki.py` | 339–350 |
| 8 | Ölçüm kalite kontrolü ve `OLCUM_GECERSIZ` | `WP8_canli_tahmin_onceki.py` | 352–359, 416–419 |
| 8 | Canlı karar akışı (RF + kontroller) | `WP8_canli_tahmin_onceki.py` | 377–419 |
| 8 | Yetersiz lazer sinyali kontrolü (defter Şekil 2) | `src/laser_detection.py` | 196–198 |
| 9 | Üç görüntü çiftinin medyan profiliyle birleştirilmesi | `WP8_canli_tahmin_onceki.py` | 129–146 |
| 9 | Kumaşa özel düz referans (kalibrasyon) okuma | `WP8_canli_tahmin_onceki.py` | 150–211 |
| 9 | Beş konumlu tarama kararı (deneme sürümü) | `WP8_tarama_karar_v3.py` | 21–30, 73–93 |
| 9 | Kamerayı bırakma ve eski sonuçları temizleme (defter Şekil 3) | `app.py` | 136–142, 367–397 |
| 10 | Oturum bazlı çapraz doğrulama (LeaveOneGroupOut) | `WP8_canli_model_egit.py` | 143–174 |
| 10 | Kat izinin kapsam dışı bırakılması, özellik setleri | `WP8_canli_model_egit.py` | 25–53 |
| 10 | 36 aday ayarın karşılaştırılması ve seçim ölçütü | `WP8_canli_model_egit.py` | 214–257 |
| 11 | Odak seçimi (netlik puanı) | `WP8_optik_dogrulama_v4.py` | 30–68 |
| 11 | 5 mm basamakla optik doğrulama | `WP8_optik_dogrulama_v4.py` | 136–175 |
| 11 | Geri çekilen mm tahmini (doğrusal formül) | `WP8_canli_tahmin.py` | 73–74, 467–471 |
| 12 | Doğruya göre sapma aralığı (%1–99), ilk sürüm | `cizgi_sapma_surumleri/ilk_surum/WP8_cizgi_sapma_karar.py` | 66–72 |
| 12 | Kumaşa özel eşik ve kanıt sayısı, ilk sürüm | `cizgi_sapma_surumleri/ilk_surum/WP8_cizgi_sapma_karar.py` | 98–112 |
| 12 | Çizgi kalınlığı (ağırlıklı standart sapma) | `cizgi_sapma_surumleri/r2/WP8_cizgi_sapma_karar.py` | 50–80 |
| 12 | Yerel kalınlık anomalisi | `cizgi_sapma_surumleri/r2/WP8_cizgi_sapma_karar.py` | 112–121 |
| 12 | Masaüstü sapma hesabı: sağlam doğru uydurma (defter Ek-1) | `src/laser_detection.py` | 38–70 |
| 13 | R3: eşik ve toplu konum zarfı | `WP8_cizgi_sapma_karar.py` | 159–180 |
| 13 | R3: üç taramada en az iki kanıt | `WP8_cizgi_sapma_karar.py` | 182–202 |
| 13 | R4: toplu kaymanın kanıttan çıkarılması | `../wp9_birlesik_arayuz/wp8_kabariklik_modulu/WP8_cizgi_sapma_karar.py` | 196–205 |

### Birleşik arayüz ve masaüstü uygulaması (Gün 18–20)

| Gün | Konu | Dosya | Satır |
| --- | --- | --- | --- |
| 18 | Leke/yırtık eşikleri ve 3 kareden 2 oy kuralı (Pi) | `staj2_deneyleri/wp9_birlesik_arayuz/wp9_ortak.py` | 13–15, 51–78 |
| 18 | Canlı analiz sonucunun işlenmesi (Pi arayüzü) | `staj2_deneyleri/wp9_birlesik_arayuz/wp9_arayuz.py` | 336–372 |
| 18 | Kabarıklık testinin başlatılması (R4 modülü) | `staj2_deneyleri/wp9_birlesik_arayuz/wp9_arayuz.py` | 374–459 |
| 18 | Birleşik genel karar | `staj2_deneyleri/wp9_birlesik_arayuz/wp9_arayuz.py` | 461–483 |
| 19 | Model giriş boyutları ve masaüstü lazer eşiği | `src/config.py` | 31, 47, 58 |
