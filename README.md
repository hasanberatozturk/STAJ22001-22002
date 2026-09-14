# Kumaş Kusur Tespit Sistemi

Bu proje, staj çalışmam kapsamında kumaş üzerindeki leke, yırtık ve yüzey
kabarıklıklarını kamera görüntüsüyle tespit etmek için geliştirdiğim bir
prototiptir.

Sistem ilk olarak Raspberry Pi, kamera ve çizgi lazer ile çalışacak şekilde
tasarlandı. Raspberry Pi arızalandığı için geliştirme ve denemeler şimdilik
bilgisayarda, OpenCV'nin gördüğü bir kamera üzerinden devam ediyor. Son hedef;
kamera, aydınlatma ve lazerin sabit olduğu düzeneği tekrar Raspberry Pi üzerine
taşımaktır.

## Sistem nasıl çalışıyor?

Program iki ayrı kontrol yapıyor:

1. **RGB kontrolü:** Lazer kapalıyken leke ve yırtık modelleri çalışır.
2. **Lazer kontrolü:** Lazer kapalı ve açık iki görüntü karşılaştırılarak yüzeyde
   kabarıklık olup olmadığı hesaplanır.

Yırtık kontrolünde önce YOLO modeli şüpheli bölgeyi bulur. Bulunan bölge gerektiğinde
ikinci bir sınıflandırma modeliyle kontrol edilir. Yırtık bölgesi leke hesabından
çıkarıldığı için aynı yırtığın ayrıca leke sayılması azaltılır. Bir kumaşta birden
fazla kusur bulunursa sonuçlar `LEKE + YIRTIK + KABARIKLIK` biçiminde birlikte
gösterilebilir.

## Güncel durum

- Leke ve yırtık tespiti canlı kamerada birlikte çalışıyor.
- Açık renkli kumaşlardaki silik lekeler için ek görüntü kontrolü bulunuyor.
- Kabarıklık ölçümü arayüzdeki iki fotoğraflı lazer adımıyla yapılıyor.
- Yeni bir kusur bulunduğunda bilgisayardan kısa sesli uyarı verilebiliyor.
- Kamera ve model hesapları arayüzü kilitlememesi için ayrı işlerde çalıştırılıyor.
- Kabarıklık bölümü prototip aşamasında. Lazer parlaklığı, kumaş gölgesi ve kamera
  açısı sonucu doğrudan etkileyebiliyor.

## Kullanılması planlanan donanımlar

- Raspberry Pi
- Raspberry Pi kamera modülü veya USB kamera
- Çizgi lazer
- Sabit ve dağınık aydınlatma
- Kumaşı düz tutan bir yüzey veya taşıma düzeneği

## Kurulum

Python 3.11 veya 3.12 ile sanal ortam oluşturun:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Model ağırlıkları boyutları nedeniyle Git deposuna eklenmez. Uygulama için gereken
dosya adları [models/README.md](models/README.md) içinde listelenmiştir.

## Çalıştırma

```powershell
.\.venv\Scripts\Activate.ps1
python app.py
```

### RGB testi

1. Lazeri kapatın.
2. **Canlı Testi Başlat** düğmesine basın.
3. Leke ve yırtık sonuçlarının birkaç kontrol sonunda sabitlenmesini bekleyin.

Program kamera girişlerini sırayla dener. Seçilen kamera kaynağı ve görüntü boyutu
ekranın üst bölümünde gösterilir.

Üst bölümdeki **Ses Açık / Ses Kapalı** düğmesiyle kusur uyarısı kontrol edilebilir.
Aynı kusur ekranda kaldığı sürece ses sürekli tekrarlanmaz.

### Kabarıklık testi

1. Kumaş ve kamera sabitken, lazer kapalı durumda **Lazer Kapalı Fotoğrafı Al**
   düğmesine basın.
2. Kumaşı oynatmadan lazeri açın ve kameranın ışığa uyum sağlaması için yaklaşık
   bir saniye bekleyin.
3. **Lazer Açık Fotoğrafı Al** düğmesine basın.
4. Sonucu gördükten sonra lazeri kapatın ve **RGB Testine Dön** düğmesine basın.

Düğmeye basıldığı anda son üç kamera karesinin ortanca görüntüsü kullanılır. Bu
yöntem küçük titreşimlerin ve anlık pozlama değişimlerinin etkisini azaltır. Lazerin
ortası beyaza dönecek kadar parlaksa kamera kırmızı renk bilgisini kaybedebilir. Bu
durumda lazer gücü veya kamera pozlaması azaltılmalıdır.

## Proje yapısı

```text
app.py                    Masaüstü arayüzü ve canlı kamera akışı
src/config.py             Kamera, model ve karar ayarları
src/defect_detection.py   Leke ve yırtık tespiti
src/laser_detection.py    Lazer çizgisi ve kabarıklık hesabı
tests/                    Temel davranış kontrolleri
tools/                    Veri toplama, eğitim ve inceleme araçları
models/                   Uygulamada kullanılan model ağırlıkları
data/                     Toplanan ve etiketlenen görüntüler
archive/                  Eski deneyler ve eğitim çıktıları
```

`data/`, `archive/`, model ağırlıkları, eğitim çıktıları ve sanal ortam `.gitignore`
ile GitHub deposunun dışında tutulur. Böylece depoda yalnızca projeyi anlamak ve
çalıştırmak için gereken kodlar bulunur.

## Yardımcı araçlar

| Komut | Amaç |
| --- | --- |
| `python tools/collect_data.py` | Kameradan yeni veri toplar. |
| `python tools/show_labels.py` | YOLO etiket kutularını görüntüler. |
| `python tools/test_images.py` | Kayıtlı görüntülerde leke ve yırtık sonucunu kontrol eder. |
| `python tools/test_tear_model.py` | Yırtık modelini etiketli veriyle değerlendirir. |
| `python tools/train_tear_model.py` | Yeni bir yırtık model adayı eğitir. |

Eğitim aracı yeni modeli doğrudan uygulamaya bağlamaz. Sonuçlar kontrol edildikten
sonra kullanılacak model elle seçilir.

## Kontrolleri çalıştırma

```powershell
python tests/test_defects.py
python tests/test_laser.py
```

Bu testler kamera açmadan temel leke, yırtık ve iki fotoğraflı lazer hesabını kontrol eder.

## Bilinen sınırlamalar

- Sonuçlar kamera yüksekliği, ışık, kumaşın duruşu ve çekim açısına bağlıdır.
- Parlak ve çok kırışık kumaşlar hem RGB hem lazer kontrolünü zorlaştırabilir.
- Lazer ölçümünde kapalı ve açık fotoğraf arasında kumaşın oynatılmaması gerekir.
- Raspberry Pi üzerinde ses kullanılacaksa ayrıca hoparlör veya buzzer bağlanmalıdır.
- Endüstriyel kullanım öncesinde daha fazla kumaşla uzun süreli test yapılmalıdır.

Bu çalışma eğitim amaçlı bir staj projesidir; henüz endüstriyel ölçüm cihazı olarak
değerlendirilmemelidir.
