# Staj-1 deney araçları

Bu klasör kamera ve çizgi lazer deneylerini ana uygulamadan ayrı tutar.
`app.py`, `src/`, modeller ve canlı karar akışı değiştirilmemiştir.

## Kaynak ve kapsam

Kodlar yerel arşivdeki
`archive/staj_belgeleri/docs/Staj1_Eski_Sohbet_Kanitlari/kod_ve_terminal_kaynaklari/`
dosyalarından uyarlanmıştır. Arşivdeki asıllar korunur. Bilgisayara özgü yollar
kaldırılmış, giriş seçenekleri ve üzerine yazmayı engelleyen kontroller eklenmiştir.
Bu sürüm, geçmişteki bir terminal oturumunun birebir kaydı veya rapordaki sayısal
sonuçların yeniden üretildiğinin kanıtı değildir. Yeni çalıştırmalar yeni sonuç üretir.

| Dosya | İlgili çalışma | Ürettiği çıktı |
| --- | --- | --- |
| `kamera_kalibrasyon_v2.py` | Satranç deseniyle kamera kalibrasyonu | Kamera matrisi, distorsiyon, RMS/RMSE, işaretli ve düzeltilmiş görüntüler |
| `lazer_pozlama_taramasi.sh` | Farklı pozlamalarda lazer görünürlüğü | Lazer açık/kapalı JPEG ve JSON metadata |
| `yerel_yukselti_cekimi.sh` | Düz yüzey ve 10 kat kâğıtla yerel yükselti | Dört koşulda üçer tekrar, toplam 12 JPEG ve metadata |
| `yerel_yukselti_analizi.py` | Yerel çizgi sapması ve tekrar edilebilirlik | Profil CSV, sonuç JSON, özet PNG ve Markdown |

Bunlar Random Forest, SVM veya YOLO eğitim kodları değildir.

## Python araçları

Projenin sanal ortamını etkinleştirin. NumPy, OpenCV ve Pillow gereklidir;
ana `requirements.txt` bu bağımlılıkları içerir. Komutları proje kökünde çalıştırın.

### Kamera kalibrasyonu

```powershell
python staj1_deneyleri/kamera_kalibrasyon_v2.py --girdi "data/kalibrasyon/ham" --ic-kose 9 7 --kare-mm 20
```

Giriş dosyaları `CALv2_*.jpg` adında, aynı çözünürlükte olmalıdır.
En az sekiz görüntüde desen bulunmalıdır. Farklı açılardan çekilmiş gerçek
kalibrasyon görüntülerini kullanın; tek görüntünün kopyaları uygun değildir.

**İç köşe sayısını fiziksel deseninizden kontrol edin.** Arşiv kaynak kodunda
`8 x 6`, arşivdeki sayısal sonuç kaydında `9 x 7` iç köşe yazmaktadır.
Bu uyuşmazlık nedeniyle varsayılan seçilmemiştir: `--ic-kose` zorunludur.
9 x 7 kareli desenin iç köşesi 8 x 6; 10 x 8 kareli desenin iç köşesi 9 x 7 olur.
Yukarıdaki komut yalnızca 9 x 7 iç köşeli, 20 mm kareli desen için örnektir.

### Yerel yükselti analizi

```powershell
python staj1_deneyleri/yerel_yukselti_analizi.py --girdi "data/yukselti/deney_klasoru"
```

Beklenen dosyalar aşağıdaki dört grubun her biri için `01`, `02`, `03` tekrarıdır:

```text
duz_lazer_kapali_01.jpg
duz_lazer_acik_01.jpg
yukselti_10kat_lazer_kapali_01.jpg
yukselti_10kat_lazer_acik_01.jpg
```

Tüm görüntüler aynı boyutta ve aynı sabit düzenekte çekilmiş olmalıdır.
Araç RGB farkından lazer profili çıkarır; üç tekrarın medyanını alır,
kenarlardan hesaplanan genel eğimi çıkarır ve ortadaki yerel sapmayı piksel olarak
raporlar. Ölçüm milimetre cinsinden yükseklik veya kumaş kusuru sınıflandırması değildir.
Sinyal/tekrar oranı, tekrar sapması sıfırken tanımsızdır ve JSON'da `null` olur.

JSON'daki 30 cm kamera mesafesi, yaklaşık 10 cm lazer uzaklığı, yaklaşık 60 derece
açı ve 2500 µs pozlama arşiv deneyinin sabit varsayımlarıdır; program bunları
görüntüden ölçmez veya JSON kamera metadata dosyasından okumaz. Başka düzenekte
bu alanları deneyinizle eşleştirmeden ölçülmüş bilgi olarak kullanmayın.

İki Python aracı da varsayılan olarak `output/staj1/` altında yeni zaman damgalı
klasör açar. `--cikti "yeni/sonuc_klasoru"` ile yer değiştirilebilir.
Mevcut sonuç klasörlerinin üzerine yazılmaz. `output/` Git dışında tutulur.

## Raspberry Pi çekimleri

Bash ve `rpicam-still` bulunan, uyumlu kameralı Raspberry Pi üzerinde çalıştırılır:

```bash
bash staj1_deneyleri/lazer_pozlama_taramasi.sh
bash staj1_deneyleri/yerel_yukselti_cekimi.sh
```

İsteğe bağlı ilk argüman çıktı köküdür; örneğin:

```bash
bash staj1_deneyleri/yerel_yukselti_cekimi.sh /home/pi/deneyler
```

Varsayılan çıktılar `output/staj1/pozlama/` ve `output/staj1/yukselti/`
altındaki benzersiz klasörlere gider. Betikler lazeri GPIO ile kontrol etmez;
kullanıcıdan lazeri açıp kapatmasını ve Enter ile onaylamasını ister.
Kamera, numune ve aydınlatma sabit tutulmalıdır. Arşivden gelen beyaz dengesi,
odak ve pozlama ayarları her kamera/düzeneğe uygun olmayabilir; çekim öncesi kontrol edin.
Lazer ışınına ve yansımasına doğrudan bakmayın.

## Yazılım kontrolleri

```powershell
python -m unittest discover -s staj1_deneyleri -p "test_*.py" -v
```

Testler geçici sentetik görüntüler kullanır; fiziksel deney doğruluğunu veya
rapor sonuçlarını doğrulamaz. Kamera ve lazer betikleri için gerçek donanımla
ayrıca kontrol gerekir.
