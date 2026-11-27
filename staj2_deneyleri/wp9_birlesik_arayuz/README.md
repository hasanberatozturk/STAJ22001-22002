# WP9 Birlesik Kumas Kusur Arayuzu

Bu paket, basarili leke modelini ve WP8 R3 kabariklik modulunu degistirmeden
yeni yirtik siniflandirma modeliyle birlestirir.

## Canli calisma mantigi

Ana kullanim dosya secmek degildir. Operator `CANLI TESTI BASLAT` dugmesine
bastiginda kamera kesintisiz acilir, goruntu ekranda canli gosterilir ve sistem
yaklasik her saniye otomatik analiz yapar. Son uc analizden cogunluk karariyla
ekranda anlik olarak `NORMAL`, `LEKE`, `YIRTIK` veya `LEKE+YIRTIK` gosterilir.
Kumas degistirildiginde yeni durum ekrana otomatik yansir. `CANLI TESTI DURDUR`
dugmesi kamerayi guvenli bicimde kapatir.

Canli sistem, basarili saha kabul cekimleriyle ayni 2304x1296 ana kareyi analiz
eder. Dokunmatik onizleme icin ayri 640x360 akisi kullanilir; bu nedenle ekran
akici kalirken leke modeline yuksek cozunurluklu kare gider. Karar satirinda son
leke ve yirtik skor yuzdeleri de gosterilir.

Picamera2 `capture_array()` verisi PIL ile kullanildigi icin iki akista da
`BGR888` istenir; Picamera2 adlandirmasinda bu secim tamponda gercek RGB kanal
sirasini verir. Boylece kirmizi/mavi kanal degisimi ve cyan onizleme onlenir.

## Karar yapisi

- Leke: dondurulmus `leke_best_nihai.pt`, esik 0.58.
- Yirtik: yeni `yirtik_best_wp9.pt`, esik 0.50.
- RGB saha karari: canli akistaki son 3 analizden en az 2 olumlu oy.
- Kabariklik: degistirilmemis `WP8-CIZGI-SAPMA-FINAL-R3-20260823` lazer modulu.
- Olası birlesik sonuclar: `NORMAL`, `LEKE`, `YIRTIK`, `LEKE+YIRTIK` ve
  lazer testi de calistirildiginda `...+KABARIKLIK`.

## Raspberry Pi kurulumu

```bash
cd ~/WP9_BIRLESIK_ARAYUZ_20260826
chmod +x kurulum.sh baslat.sh
./kurulum.sh
./baslat.sh
```

Kurulum Raspberry Pi 5 ARM64 icin CPU-only PyTorch 2.6.0 kullanir. NVIDIA/CUDA
paketleri indirilmez. `ImageTk` destegi Raspberry Pi OS paket yoneticisinden
`python3-pil.imagetk` ile kurulur.

Onceki bir kurulum NVIDIA paketi indirmeye calisirken yarida kaldiysa, guncel
paketi Pi'ye yeniden acin ve ayni klasorde `./kurulum.sh` komutunu tekrar
calistirin. Betik mevcut `.venv` ortamını onararak eksik kurulumlari tamamlar.

## Dokunmatik ekran ve otomatik acilis

Raspberry Pi OS masaustunde dokunmatik ekran goruntu ve dokunma aygiti olarak
tanindiktan sonra arayuzu tam ekran acmak ve her masaustu oturumunda otomatik
baslatmak icin:

```bash
./dokunmatik_kur.sh
```

Arayuz tam ekran acilir ve ekran yonunu otomatik algilar. 1024x600 yatay
ekranda canli goruntu solda, kontroller sagda; 600x1024 portre ekranda canli
goruntu ustte, kusur kartlari ve tum dokunmatik dugmeler altta yer alir.
`TAM EKRAN` dugmesi pencere moduna gecis yapar; `CIKIS` uygulamayi kapatir.

### SSH'de `no $DISPLAY` hatasi

Tkinter arayuzu grafik masaustunde calisir. SSH terminalinde `$DISPLAY` bos
olabilir. Guncel `baslat.sh`, ayni kullanicinin acik dokunmatik masaustu
oturumunu otomatik bulmayi dener. Masaustu acik degilse Raspberry Pi'yi
`Desktop Autologin` ile baslatin; `dokunmatik_kur.sh` tarafindan kurulan
otomatik acilis, masaustu oturumu acildiktan 8 saniye sonra arayuzu baslatir.
Otomatik acilis hatalari `~/wp9-autostart.log` dosyasina yazilir.

RGB testinde lazer kapali tutulur. Kabariklik testi ayri dugmeden baslatilir;
lazer acma/kapama yonlendirmeleri WP8 terminalinde izlenir. Olcum tamamlaninca
`nihai_sonuc.json` arayuz tarafindan otomatik izlenir; sonuc KABARIKLIK kartina
ve genel karar alanina kendiliginden aktarilir. `SON LAZER SONUCUNU GOSTER`
dugmesi yalnizca eski bir sonucu yeniden cagirmak icin yedektir. Kabariklik
testi baslatilirken canli RGB kamera otomatik durdurulur.

R4 kabariklik kararinda kumasin cok az yer degistirmesinden etkilenebilen
`toplu_kayma_var` tani amaciyla raporlanmaya devam eder, ancak tek basina kusur
karari vermez. KUSUR sonucu icin lazer cizgisinin sekil veya kalinlik
bozulmasinin en az iki ayri taramada tekrarlanmasi gerekir. Bu degisiklik,
R3'te duz kumasin yalnizca toplu cizgi konumu nedeniyle KUSUR sayilabildigi
yanlis pozitif durumu giderir.

Canli kareler ve kararlar `~/WP9_KAYITLAR/<oturum>/` altinda saklanir.

## Istege bagli cevrimdisi dogrulama

```bash
source .venv/bin/activate
python3 wp9_cli_test.py kare1.jpg kare2.jpg kare3.jpg --cikti sonuc.json
```

Bu komut yalnizca teknik dogrulama icindir; operator arayuzunun ana calisma
sekli canli kameradir.

## Dogrulama ozeti

- Yeni arşiv: 4 kumas, 32 normal, 60 yirtik, toplam 92 kare.
- Mavi saten tamamen holdout iken: 23/23 dogru.
- Ayrı saha oturumu: kare bazında 40/42 dogru (%95,24).
- Uclu fiziksel grup cogunlugu: 14/14 dogru.
- Mavi saten leke+yirtik: 15/15 karede iki model de olumlu.

Bu pilot, yarinki WP10 saha kabul testleri tamamlanmadan uretim sistemi olarak
ilan edilmemelidir.
