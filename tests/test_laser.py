"""Arayüzde kullanılan iki fotoğraflı lazer yöntemini kontrol eder."""

import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.laser_detection import lazer_fotograflarini_karsilastir


def dogrula(condition: bool, error_message: str) -> None:
    """Sonuç yanlışsa testi anlaşılır bir mesajla durdurur."""
    if not condition:
        raise RuntimeError(error_message)


def lazer_kapali_fotograf() -> np.ndarray:
    """Lazer kapalıyken görülen düz ve koyu bir örnek hazırlar."""
    return np.full((240, 360, 3), 45, dtype=np.uint8)


def lazer_acik_fotograf(
    bump_height: float = 0.0,
    line_width: int = 2,
) -> np.ndarray:
    """Gerçek kameraya gerek kalmadan yapay bir lazer çizgisi hazırlar."""
    frame = lazer_kapali_fotograf()
    height, width = frame.shape[:2]
    for x in range(25, width - 25):
        rise = bump_height * np.exp(-((x - width / 2) / 30.0) ** 2)
        y = int(105 + 0.05 * x - rise)
        cv2.circle(frame, (x, y), line_width, (45, 45, 255), -1)
    return frame


def normal_ve_kabarik_kontrolu() -> None:
    """Düz çizgiyle bükülmüş çizginin ayrıldığını kontrol eder."""
    off_frame = lazer_kapali_fotograf()
    normal = lazer_fotograflarini_karsilastir(
        off_frame,
        lazer_acik_fotograf(),
    )
    bump_result = lazer_fotograflarini_karsilastir(
        off_frame,
        lazer_acik_fotograf(14.0),
    )

    dogrula(not normal.has_bump, "Düz lazer çizgisi kabarık sayıldı")
    dogrula(bump_result.has_bump, "Kabarık lazer çizgisi bulunamadı")


def parlak_ve_dikey_lazer_kontrolu() -> None:
    """Kalın ve dikey görünen lazer çizgisini kontrol eder."""
    off_frame = lazer_kapali_fotograf()
    bright_normal = lazer_fotograflarini_karsilastir(
        off_frame,
        lazer_acik_fotograf(line_width=7),
    )
    dogrula(
        not bright_normal.has_bump,
        "Parlak düz lazer çizgisi kabarık sayıldı",
    )

    portrait_off = cv2.rotate(off_frame, cv2.ROTATE_90_CLOCKWISE)
    portrait_on = cv2.rotate(
        lazer_acik_fotograf(14.0),
        cv2.ROTATE_90_CLOCKWISE,
    )
    portrait_result = lazer_fotograflarini_karsilastir(portrait_off, portrait_on)
    dogrula(portrait_result.direction == "dikey", "Dikey lazer yönü bulunamadı")
    dogrula(portrait_result.has_bump, "Dikey lazerde kabarıklık bulunamadı")


def kisa_bosluk_kontrolu() -> None:
    """Çizgideki küçük gölge boşluklarının sonucu bozmadığını kontrol eder."""
    off_frame = lazer_kapali_fotograf()
    on_frame = lazer_acik_fotograf(14.0)
    for start in (90, 180, 270):
        on_frame[:, start:start + 8] = 45

    result = lazer_fotograflarini_karsilastir(off_frame, on_frame)
    dogrula(result.has_bump, "Boşluklu lazer çizgisi okunamadı")


def hatali_fotograf_kontrolu() -> None:
    """Lazer olmayan veya boyutu farklı fotoğrafların kabul edilmediğini kontrol eder."""
    off_frame = lazer_kapali_fotograf()
    invalid_pairs = (
        (off_frame, off_frame.copy()),
        (off_frame, np.full((200, 300, 3), 45, dtype=np.uint8)),
    )

    for first, second in invalid_pairs:
        try:
            lazer_fotograflarini_karsilastir(first, second)
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
