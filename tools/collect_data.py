"""Kameradan etiketli ham kumaş görüntüleri toplar."""

from datetime import datetime
from pathlib import Path
import sys

import cv2


ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from src.camera import kamera_ac  # noqa: E402

LABEL_KEYS = {
    ord("n"): "normal",
    ord("l"): "stain",
    ord("y"): "tear",
    ord("b"): "combined",
}


def ana_program() -> None:
    """Tuşla seçilen etikete göre kamera karesini data/raw içine kaydeder."""
    save_dir = ROOT_DIR / "data" / "raw"

    for label in LABEL_KEYS.values():
        (save_dir / label).mkdir(parents=True, exist_ok=True)

    camera, _ = kamera_ac()
    if camera is None:
        raise RuntimeError("Kamera acilamadi. Kamera baglantisini kontrol edin.")

    print("N: normal | L: leke | Y: yirtik | B: birlesik | Q: cikis")

    try:
        while True:
            read_ok, frame = camera.read()

            if not read_ok:
                print("Kameradan goruntu alinamadi.")
                break

            preview = frame.copy()

            cv2.putText(
                preview,
                "N: NORMAL  L: LEKE  Y: YIRTIK  B: BIRLESIK  Q: CIKIS",
                (25, 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (0, 255, 255),
                2,
            )

            cv2.imshow("Veri Toplama", preview)

            key = cv2.waitKey(1) & 0xFF

            if key == ord("q"):
                break

            if key in LABEL_KEYS:
                label = LABEL_KEYS[key]
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                save_path = save_dir / label / f"{label}_{timestamp}.jpg"

                encoded_ok, image_bytes = cv2.imencode(
                    ".jpg",
                    frame,
                    [cv2.IMWRITE_JPEG_QUALITY, 95],
                )

                saved = (
                    encoded_ok
                    and save_path.write_bytes(image_bytes.tobytes()) > 0
                )

                if saved:
                    print(f"Kaydedildi: {save_path}")
                else:
                    print(f"Kaydedilemedi: {save_path}")

    finally:
        camera.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    ana_program()
