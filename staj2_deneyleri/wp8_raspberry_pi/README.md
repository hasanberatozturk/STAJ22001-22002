# WP8 Raspberry Pi model yükleme testi

Bu paket canlı kameraya geçmeden önce WP7 Random Forest modelinin Raspberry
Pi'de açılabildiğini ve kayıtlı K011 test verisinde aynı sonucu verdiğini kontrol
eder.

## Raspberry Pi'ye aktarım

Windows PowerShell'de paketin bulunduğu üst klasörde:

```powershell
scp -r .\WP8_RPI_model_testi_20260819 hasanberat@kumas-pi5:/home/hasanberat/
```

## Raspberry Pi'de kurulum

```bash
cd /home/hasanberat/WP8_RPI_model_testi_20260819
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt
```

## Test

```bash
python3 WP8_offline_tahmin.py \
  --model wp7_random_forest_degerlendirme.joblib \
  --bilgi wp7_model_bilgileri.json \
  --csv wp7_ozellikler.csv \
  --split test \
  --cikti sonuclar
```

Beklenen temel sonuç:

```text
Kullanılan özellik sayısı: 26
Değerlendirilen örnek sayısı: 18
dogruluk: %100.00
tn: 3
fp: 0
fn: 0
tp: 15
```

Bu test yalnızca model dosyasının Raspberry Pi ortamında doğru yüklendiğini
kanıtlar. Canlı kamera sınıflandırması için sonraki adımda üç normal D00 çiftiyle
kumaş kalibrasyonu ve lazer açık/kapalı görüntü çiftinden özellik çıkarımı
eklenecektir.
