"""Hazırlanan yırtık kutularını tek bir kontrol görüntüsünde gösterir."""

from pathlib import Path

import cv2
import numpy as np


ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data" / "tear_detection"
OUTPUT_PATH = ROOT_DIR / "reports" / "tear_label_preview.jpg"


def kutulari_oku(label_file: Path, width: int, height: int):
    for row in label_file.read_text(encoding="utf-8").splitlines():
        _, center_x, center_y, box_width, box_height = map(float, row.split())
        yield (
            int((center_x - box_width / 2) * width),
            int((center_y - box_height / 2) * height),
            int((center_x + box_width / 2) * width),
            int((center_y + box_height / 2) * height),
        )


def resmi_hazirla(file: Path) -> np.ndarray:
    frame = cv2.imdecode(np.fromfile(file, dtype=np.uint8), cv2.IMREAD_COLOR)
    height, width = frame.shape[:2]
    label = DATA_DIR / "labels" / file.parent.name / f"{file.stem}.txt"
    for left, top, right, bottom in kutulari_oku(label, width, height):
        cv2.rectangle(frame, (left, top), (right, bottom), (0, 255, 255), 8)
    cv2.putText(
        frame,
        file.name[-38:],
        (20, 45),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.0,
        (0, 255, 255),
        3,
        cv2.LINE_AA,
    )
    frame = cv2.resize(frame, (640, 360), interpolation=cv2.INTER_AREA)
    return frame


def ana_program() -> None:
    """Yırtık etiket kutularını resimlerin üzerine çizip önizleme oluşturur."""
    selected_images = []
    for split in ("train", "val"):
        folder = DATA_DIR / "images" / split
        new_images = sorted(folder.glob("phone_pos_*.jpg"))
        old_images = []
        for group in ("K001", "K002", "K003", "K004"):
            found = next(iter(sorted(folder.glob(f"old_pos_*{group}*_01.jpg"))), None)
            if found:
                old_images.append(found)
        selected_images.extend(old_images + new_images)

    rows = []
    for index in range(0, len(selected_images), 2):
        row = [resmi_hazirla(file) for file in selected_images[index:index + 2]]
        if len(row) == 1:
            row.append(row[0] * 0)
        rows.append(cv2.hconcat(row))
    preview = cv2.vconcat(rows)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    encoded_ok, image_data = cv2.imencode(".jpg", preview)
    if not encoded_ok:
        raise RuntimeError("Kontrol goruntusu kodlanamadi")
    image_data.tofile(OUTPUT_PATH)
    print(OUTPUT_PATH)


if __name__ == "__main__":
    ana_program()
