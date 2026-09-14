"""Kameradan etiketli ham kumaş görüntüleri toplar."""

from datetime import datetime
from pathlib import Path
import sys

import cv2


ANA_KLASOR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ANA_KLASOR))

from src.config import (  # noqa: E402
    GORUNTU_GENISLIGI,
    GORUNTU_YUKSEKLIGI,
    KAMERA_LISTESI,
)



ETIKET_TUSLARI = {
    ord("n"): "normal",
    ord("l"): "stain",
    ord("y"): "tear",
    ord("b"): "combined",
}


def ana_program() -> None:
    """Tuşla seçilen etikete göre kamera karesini data/raw içine kaydeder."""
    kayit_klasoru = ANA_KLASOR / "data" / "raw"

    for etiket in ETIKET_TUSLARI.values():
        (kayit_klasoru / etiket).mkdir(parents=True, exist_ok=True)

    kamera_numarasi, sistem_adi = KAMERA_LISTESI[0]
    kamera_sistemi = cv2.CAP_MSMF if sistem_adi == "MSMF" else cv2.CAP_DSHOW
    kamera = cv2.VideoCapture(kamera_numarasi, kamera_sistemi)
    kamera.set(cv2.CAP_PROP_FRAME_WIDTH, GORUNTU_GENISLIGI)
    kamera.set(cv2.CAP_PROP_FRAME_HEIGHT, GORUNTU_YUKSEKLIGI)

    if not kamera.isOpened():
        raise RuntimeError("Kamera acilamadi. Kamera baglantisini kontrol edin.")

    print("N: normal | L: leke | Y: yirtik | B: birlesik | Q: cikis")

    try:
        while True:
            okundu, kare = kamera.read()

            if not okundu:
                print("Kameradan goruntu alinamadi.")
                break

            onizleme = kare.copy()

            cv2.putText(
                onizleme,
                "N: NORMAL  L: LEKE  Y: YIRTIK  B: BIRLESIK  Q: CIKIS",
                (25, 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (0, 255, 255),
                2,
            )

            cv2.imshow("Veri Toplama", onizleme)

            tus = cv2.waitKey(1) & 0xFF

            if tus == ord("q"):
                break

            if tus in ETIKET_TUSLARI:
                etiket = ETIKET_TUSLARI[tus]
                zaman = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                kayit_yolu = kayit_klasoru / etiket / f"{etiket}_{zaman}.jpg"

                kodlandi, kodlanmis_resim = cv2.imencode(
                    ".jpg",
                    kare,
                    [cv2.IMWRITE_JPEG_QUALITY, 95],
                )

                kaydedildi = (
                    kodlandi
                    and kayit_yolu.write_bytes(kodlanmis_resim.tobytes()) > 0
                )

                if kaydedildi:
                    print(f"Kaydedildi: {kayit_yolu}")
                else:
                    print(f"Kaydedilemedi: {kayit_yolu}")

    finally:
        kamera.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    ana_program()
