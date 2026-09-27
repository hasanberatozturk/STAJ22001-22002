"""Leke ve yırtık kararını kayıtlı kamera karelerinde sınar."""

from pathlib import Path
import sys

import cv2
import numpy as np


ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from src.defect_detection import KusurTespiti  # noqa: E402


def resmi_oku(file: Path) -> np.ndarray | None:
    image_bytes = np.fromfile(file, dtype=np.uint8)
    if image_bytes.size == 0:
        return None
    return cv2.imdecode(image_bytes, cv2.IMREAD_COLOR)


def ana_program() -> None:
    """Kaydedilmiş görüntüleri çalıştırıp beklenen ve bulunan sonuçları yazar."""
    detector = KusurTespiti()
    detector.hazirla()
    save_dir = ROOT_DIR / "data" / "raw"
    expected_results = {
        "normal": (False, False),
        "stain": (True, False),
        "tear": (False, True),
        "combined": (True, True),
    }
    correct_tears = 0
    correct_stains = 0
    total = 0

    print("grup     | karar        | leke | kutu/kontrol | adet | dosya")
    for group, (expect_stain, expect_tear) in expected_results.items():
        for file in sorted((save_dir / group).glob("*.jpg")):
            frame = resmi_oku(file)
            if frame is None:
                print(f"Atlandı (okunamadı): {file.name}")
                continue
            result = detector.kontrol_et(frame)
            total += 1
            correct_tears += result.has_tear == expect_tear
            correct_stains += result.has_stain == expect_stain
            decision = "+".join(
                name for name, found in (("LEKE", result.has_stain), ("YIRTIK", result.has_tear))
                if found
            ) or "NORMAL"
            check = (
                f"{result.tear_check_score:4.2f}"
                if result.tear_checked
                else "  --"
            )
            print(
                f"{group:8} | {decision:12} | {result.stain_score:4.2f} "
                f"| {result.tear_score:4.2f}/{check} "
                f"| {len(result.tear_boxes):4} | {file.name}"
            )

    print(f"\nYırtık ayrımı: {correct_tears}/{total}")
    print(f"Leke ayrımı:   {correct_stains}/{total}")


if __name__ == "__main__":
    ana_program()
