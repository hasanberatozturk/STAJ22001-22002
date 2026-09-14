"""Programda kullanılan ayarlar."""

from pathlib import Path


ANA_KLASOR = Path(__file__).resolve().parents[1]
MODEL_KLASORU = ANA_KLASOR / "models"

# Kamera ayarları
# Program listedeki seçenekleri sırayla dener ve görüntü veren ilk kamerayı kullanır.
KAMERA_LISTESI = (
    (0, "MSMF"),
    (0, "DSHOW"),
    (2, "MSMF"),
    (1, "DSHOW"),
    (1, "MSMF"),
)
GORUNTU_GENISLIGI = 1280
GORUNTU_YUKSEKLIGI = 720
KARE_HIZI = 30

# Canlı leke-yırtık kararı
# Her kareyi analiz etmek kamerayı yavaşlattığı için kontroller aralıklı yapılıyor.
GORUNTU_KONTROL_ARALIGI = 0.50
# Son 3 kareden en az 2 tanesi kusurlu derse ekranda VAR sonucu gösteriliyor.
KARAR_KARE_SAYISI = 3
GEREKEN_OY = 2

# Leke modeli ve karar sınırları
LEKE_MODEL_YOLU = MODEL_KLASORU / "stain_model.pt"
LEKE_GORUNTU_BOYUTU = 384
LEKE_ESIGI = 0.58
BIRLIKTE_LEKE_ESIGI = 0.25
# Dikey kamera görüntüsünde orta bölüm ayrıca kontrol ediliyor.
DIKEY_GORUNTU_ORANI = 1.35

# Açık krem kumaştaki düşük kontrastlı leke desteği
ACIK_KUMAS_PARLAKLIK_SINIRI = 145.0
ACIK_LEKE_RENK_FARKI = 7.0
ACIK_LEKE_PARLAKLIK_FARKI = 6.0
ACIK_LEKE_EN_KUCUK_ALAN = 0.001
ACIK_LEKE_EN_BUYUK_ALAN = 0.08

# Yırtık modeli ve kontrol modeli
YIRTIK_MODEL_YOLU = MODEL_KLASORU / "tear_detector.pt"
YIRTIK_KONTROL_MODEL_YOLU = MODEL_KLASORU / "tear_classifier.pt"
YIRTIK_GORUNTU_BOYUTU = 640
YIRTIK_KONTROL_BOYUTLARI = (224, 320)
YIRTIK_ADAY_ESIGI = 0.13
# Kutu puanı bu değeri geçerse ikinci model düşük puan verse de yırtık kabul edilir.
YIRTIK_GUCLU_ESIGI = 0.40
YIRTIK_KONTROL_ESIGI = 0.50

# Çizgi lazeri ve kabarıklık ayarları
# Güncel sistemde lazer kapalı ve lazer açık iki fotoğraf karşılaştırılıyor.
# Lazer kapalı ve açık iki fotoğraf karşılaştırıldığında bu sapma aşılırsa
# kabarıklık kabul edilir. Eski düz yüzey çekimlerinde 5-6 px doğal oynama
# görüldüğü için sınırı bunun biraz üstünde tutuyorum.
LAZER_IKI_KARE_ESIGI = 8.0
# Düğmeye basıldığında son üç kare birleştirilir. Bu, telefon kamerasındaki küçük
# pozlama değişimini tek kareye göre daha az etkili hale getirir.
LAZER_FOTOGRAF_KARE_SAYISI = 3
LAZER_KESINTISIZ_UZUNLUK = 0.30
# Seçilen uzun şeridin en az bu kadarı gerçek kırmızı lazer pikseli olmalıdır.
LAZER_ISLEM_GENISLIGI = 640
LAZER_X_ALANI = (0.10, 0.90)
LAZER_Y_ALANI = (0.15, 0.85)
