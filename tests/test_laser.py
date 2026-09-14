"""Arayüzde kullanılan iki fotoğraflı lazer yöntemini kontrol eder."""

import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.laser_detection import lazer_fotograflarini_karsilastir


def dogrula(kosul: bool, hata_mesaji: str) -> None:
    """Sonuç yanlışsa testi anlaşılır bir mesajla durdurur."""
    if not kosul:
        raise RuntimeError(hata_mesaji)


def lazer_kapali_fotograf() -> np.ndarray:
    """Lazer kapalıyken görülen düz ve koyu bir örnek hazırlar."""
    return np.full((240, 360, 3), 45, dtype=np.uint8)


def lazer_acik_fotograf(
    kabariklik: float = 0.0,
    cizgi_kalinligi: int = 2,
) -> np.ndarray:
    """Gerçek kameraya gerek kalmadan yapay bir lazer çizgisi hazırlar."""
    kare = lazer_kapali_fotograf()
    yukseklik, genislik = kare.shape[:2]
    for x in range(25, genislik - 25):
        yukselme = kabariklik * np.exp(-((x - genislik / 2) / 30.0) ** 2)
        y = int(105 + 0.05 * x - yukselme)
        cv2.circle(kare, (x, y), cizgi_kalinligi, (45, 45, 255), -1)
    return kare


def normal_ve_kabarik_kontrolu() -> None:
    """Düz çizgiyle bükülmüş çizginin ayrıldığını kontrol eder."""
    kapali = lazer_kapali_fotograf()
    normal = lazer_fotograflarini_karsilastir(
        kapali,
        lazer_acik_fotograf(),
    )
    kabarik = lazer_fotograflarini_karsilastir(
        kapali,
        lazer_acik_fotograf(14.0),
    )

    dogrula(not normal.kabariklik_var, "Düz lazer çizgisi kabarık sayıldı")
    dogrula(kabarik.kabariklik_var, "Kabarık lazer çizgisi bulunamadı")


def parlak_ve_dikey_lazer_kontrolu() -> None:
    """Kalın ve dikey görünen lazer çizgisini kontrol eder."""
    kapali = lazer_kapali_fotograf()
    parlak_normal = lazer_fotograflarini_karsilastir(
        kapali,
        lazer_acik_fotograf(cizgi_kalinligi=7),
    )
    dogrula(
        not parlak_normal.kabariklik_var,
        "Parlak düz lazer çizgisi kabarık sayıldı",
    )

    dikey_kapali = cv2.rotate(kapali, cv2.ROTATE_90_CLOCKWISE)
    dikey_acik = cv2.rotate(
        lazer_acik_fotograf(14.0),
        cv2.ROTATE_90_CLOCKWISE,
    )
    dikey_sonuc = lazer_fotograflarini_karsilastir(dikey_kapali, dikey_acik)
    dogrula(dikey_sonuc.yon == "dikey", "Dikey lazer yönü bulunamadı")
    dogrula(dikey_sonuc.kabariklik_var, "Dikey lazerde kabarıklık bulunamadı")


def kisa_bosluk_kontrolu() -> None:
    """Çizgideki küçük gölge boşluklarının sonucu bozmadığını kontrol eder."""
    kapali = lazer_kapali_fotograf()
    acik = lazer_acik_fotograf(14.0)
    for baslangic in (90, 180, 270):
        acik[:, baslangic:baslangic + 8] = 45

    sonuc = lazer_fotograflarini_karsilastir(kapali, acik)
    dogrula(sonuc.kabariklik_var, "Boşluklu lazer çizgisi okunamadı")


def hatali_fotograf_kontrolu() -> None:
    """Lazer olmayan veya boyutu farklı fotoğrafların kabul edilmediğini kontrol eder."""
    kapali = lazer_kapali_fotograf()
    hatali_ciftler = (
        (kapali, kapali.copy()),
        (kapali, np.full((200, 300, 3), 45, dtype=np.uint8)),
    )

    for birinci, ikinci in hatali_ciftler:
        try:
            lazer_fotograflarini_karsilastir(birinci, ikinci)
        except ValueError:
            continue
        raise RuntimeError("Hatalı lazer fotoğrafları kabul edildi")


def ana_test() -> None:
    normal_ve_kabarik_kontrolu()
    parlak_ve_dikey_lazer_kontrolu()
    kisa_bosluk_kontrolu()
    hatali_fotograf_kontrolu()
    print("Lazer kontrolleri geçti.")


if __name__ == "__main__":
    ana_test()
