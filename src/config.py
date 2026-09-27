"""Programda kullanılan ayarlar."""

from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
MODEL_DIR = ROOT_DIR / "models"

# Kamera ayarları
# Program listedeki seçenekleri sırayla dener ve görüntü veren ilk kamerayı kullanır.
CAMERA_SOURCES = (
    (0, "MSMF"),
    (0, "DSHOW"),
    (2, "MSMF"),
    (1, "DSHOW"),
    (1, "MSMF"),
)
FRAME_WIDTH = 1280
FRAME_HEIGHT = 720
FRAME_RATE = 30

# Canlı leke-yırtık kararı
# Her kareyi analiz etmek kamerayı yavaşlattığı için kontroller aralıklı yapılıyor.
ANALYSIS_INTERVAL = 0.50
# Son 3 kareden en az 2 tanesi kusurlu derse ekranda VAR sonucu gösteriliyor.
VOTE_FRAME_COUNT = 3
REQUIRED_VOTES = 2

# Leke modeli ve karar sınırları
STAIN_MODEL_PATH = MODEL_DIR / "stain_model.pt"
STAIN_IMAGE_SIZE = 384
STAIN_THRESHOLD = 0.58
COMBINED_STAIN_THRESHOLD = 0.25
# Dikey kamera görüntüsünde orta bölüm ayrıca kontrol ediliyor.
PORTRAIT_IMAGE_RATIO = 1.35

# Açık krem kumaştaki düşük kontrastlı leke desteği
LIGHT_FABRIC_BRIGHTNESS_LIMIT = 145.0
LIGHT_STAIN_COLOR_DIFF = 7.0
LIGHT_STAIN_BRIGHTNESS_DIFF = 6.0
LIGHT_STAIN_MIN_AREA = 0.001
LIGHT_STAIN_MAX_AREA = 0.08

# Yırtık modeli ve kontrol modeli
TEAR_MODEL_PATH = MODEL_DIR / "tear_detector.pt"
TEAR_CHECK_MODEL_PATH = MODEL_DIR / "tear_classifier.pt"
TEAR_IMAGE_SIZE = 640
TEAR_CHECK_SIZES = (224, 320)
TEAR_CANDIDATE_THRESHOLD = 0.13
# Kutu puanı bu değeri geçerse ikinci model düşük puan verse de yırtık kabul edilir.
STRONG_TEAR_THRESHOLD = 0.40
TEAR_CHECK_THRESHOLD = 0.50

# Çizgi lazeri ve kabarıklık ayarları
# Lazer kapalı ve açık iki fotoğraf karşılaştırıldığında bu sapma aşılırsa
# kabarıklık kabul edilir. Düz yüzey çekimlerinde 5-6 px doğal oynama
# görüldüğü için sınırı bunun biraz üstünde tutuyorum.
LASER_BUMP_THRESHOLD = 8.0
# Düğmeye basıldığında son üç kare birleştirilir. Bu, telefon kamerasındaki küçük
# pozlama değişimini tek kareye göre daha az etkili hale getirir.
LASER_PHOTO_FRAME_COUNT = 3
LASER_MIN_LENGTH_RATIO = 0.30
# Seçilen uzun şeridin en az bu kadarı gerçek kırmızı lazer pikseli olmalıdır.
LASER_IMAGE_WIDTH = 640
LASER_X_RANGE = (0.10, 0.90)
LASER_Y_RANGE = (0.15, 0.85)
