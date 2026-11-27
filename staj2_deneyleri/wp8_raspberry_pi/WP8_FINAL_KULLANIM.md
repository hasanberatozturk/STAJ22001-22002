# WP8 final basit test

Sürüm: `WP8-CIZGI-SAPMA-FINAL-R3-20260823`

Bu sürüm yalnızca düz yüzeyli açık, koyu, desenli ve parlak kumaşlarda
belirgin kırışıklık ile kabarıklığın lazer çizgisini bozup bozmadığını ölçer.
Kat izi ve kendinden kırışık/dokulu kumaş kapsam dışıdır.

## Karar mantığı

1. Her kumaştan üç düz normal referans alınır.
2. Her ölçümde lazer çizgisine bir doğru uydurulur.
3. Çizginin bu doğrudan yüzde 1-99 sapma aralığı hesaplanır.
4. Kırışıklığın çizgiyi kaydırmadan kalınlaştırdığı durumlar için yerel çizgi
   kalınlığı değişimi de ölçülür.
5. Geniş kabarıklığın çizgiyi topluca kaydırdığı durumlar için orta profil
   konumu düz referansların oluşturduğu kumaşa özel zarfla karşılaştırılır.
6. Üç gösterge için düz referanslardan kumaşa özel güvenlik sınırı kurulur.
7. Üç taramanın en az ikisi sınırı aşarsa `KUSUR`, aksi halde `NORMAL` denir.

R3, sarı ve siyah mat kumaşların yedi kayıtlı testi üzerinde doğrulanmıştır.
Her iki kumaşta düz yüzey `NORMAL`; kırışıklık ve kabarıklıklar `KUSUR`
vermiştir. Siyah kumaştaki aynı kabarıklığın iki bağımsız testi de `KUSUR`
sonucunu üretmiştir.

Kusur kamerada görünse bile lazer çizgisini kesmiyorsa sistemin onu algılaması
beklenmez. Kırışıklık veya kabarıklık üç taramada da lazer çizgisini kesmelidir.

## Raspberry Pi üzerinde çalıştırma

```bash
cd ~/WP8_RPI_model_testi_20260819
source .venv/bin/activate
chmod +x wp8_cizgi_test_final.sh
./wp8_cizgi_test_final.sh
```

Her kumaş için yeni bir oturum açın. Sıra:

1. Düz normal yüzey
2. Belirgin kırışıklık (lazer çizgisini kesmeli)
3. Belirgin kabarıklık/sırt (lazer çizgisini kesmeli)

İlk testte normal yüzey `NORMAL` çıkmadan kusur testlerine geçmeyin.
