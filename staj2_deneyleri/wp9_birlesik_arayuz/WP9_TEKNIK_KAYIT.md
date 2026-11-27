# İş Paketi 9 - Operatör Arayüzü ve Model Birleştirme Kaydı

Tarih: 26.08.2026

Başarılı RGB leke modeli ile WP8 R3 lazer çizgisi tabanlı kabarıklık modülü
dondurulmuş, ağırlıkları ve eşikleri değiştirilmemiştir. Yeni çekilen 92 RGB
görüntü kullanılarak yırtık modeli yeniden eğitilmiştir. İlk eğitimde yalnız
lekeli L2 görüntülerinin yırtıkla karıştığı görülmüş; bu görüntüler yırtık
modeline sert negatif olarak eklenmiş, leke modeli değiştirilmemiştir.

Yeni yırtık modeli mavi saten tamamen eğitim dışında bırakıldığında 8 normal ve
15 yırtıklı görüntünün tamamını doğru ayırmıştır. Ayrı saha oturumundaki 42
karede 40 doğru sonuç elde edilmiştir. Kalan iki tek-kare hatası üçlü çekim
çoğunluk kararıyla giderilmiş ve 14 fiziksel grubun tamamı doğru
sınıflandırılmıştır. Bu nedenle WP9 arayüzü canlı akıştaki son üç ardışık RGB
analizinden en az iki oy koşulu kullanmaktadır.

Dokunmatik arayüzün ana çalışma biçimi sürekli kameradır. Operatör canlı testi
başlattığında kamera önizlemesi kesintisiz gösterilir; yaklaşık her saniye bir
kare otomatik analiz edilir ve kayan üç analiz penceresinden `NORMAL`, `LEKE`,
`YIRTIK` veya `LEKE+YIRTIK` geri bildirimi üretilir. Dosya seçimi ana arayüzden
kaldırılmıştır. Çevrimdışı üç dosya testi yalnız teknik CLI doğrulaması olarak
korunmuştur. Arayüz ayrıca WP8 kabarıklık testini başlatma, son lazer sonucunu
okuma, kusur uyarısı ve JSONL oturum kaydı işlevlerini içerir. Mavi saten
üzerindeki leke+yırtık görüntülerinde iki RGB modeli aynı anda olumlu sonuç
vermiştir.

Arayüz Raspberry Pi dokunmatik ekranında tam ekran açılacak ve 1024x600 yatay
ile 600x1024 portre yönlerini otomatik düzenleyecek şekilde güncellenmiştir.
Canlı testi başlatma/durdurma, kabarıklık testini açma, son
sonucu okuma, tam ekran geçişi ve çıkış işlemleri dokunmatik düğmelerle
yapılabilir. `dokunmatik_kur.sh` masaüstü oturumunda otomatik açılışı kurar.
WP8 kabarıklık ölçümünde lazer açma/kapatma ve kumaşı kaydırma fiziksel işlem
olarak kalır; mevcut sürüm lazeri GPIO üzerinden otomatik sürmez.

WP9 sonucu çalışan pilot olarak kabul edilmiştir. Üretim kabulü değildir.
WP10 kapsamında bağımsız fiziksel numuneler, uzun süreli çalışma, sıcaklık,
aydınlatma değişimi, yanlış alarm ve kusur kaçırma testleri yapılacaktır.

## 27.08.2026 arayüz ve kabarıklık düzeltmesi

Saha ekranındaki normal kumaş ölçümünde merkez sapması ve çizgi kalınlığı
eşikleri aşılmadığı halde yalnız toplu çizgi konumu zarf dışına çıktığı için
R3 sürümünün `KUSUR` verdiği görüldü. Toplu çizgi konumu kumaşın küçük yer ve
eğim değişiminden etkilendiği için R4 kararında tanı ölçütü olarak korundu,
ancak tek başına kusur kanıtı olmaktan çıkarıldı. Aynı ölçüm değerleriyle
yapılan geriye dönük kontrolde karar `NORMAL` oldu. Fiziksel normal ve kabarık
numune kabul testleri WP10'a bırakıldı.

Dokunmatik arayüz 600x1024 dikey ekran için daha okunaklı Türkçe başlıklar,
yüksek kontrastlı kartlar, iki satırlı büyük dokunmatik düğmeler ve sade bir
genel sonuç alanıyla yenilendi. Lazer testinin oluşturduğu en yeni
`nihai_sonuc.json` artık otomatik izlenmekte; sonuç ayrı bir düğmeye gerek
kalmadan KABARIKLIK kartına ve birleşik genel sonuca aktarılmaktadır. Manuel
`SON LAZER SONUCUNU GÖSTER` düğmesi yedek olarak korunmuştur.
