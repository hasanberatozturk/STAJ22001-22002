"""Yırtık modelinin kutu sonuçlarını kontrol eder."""

from pathlib import Path
import sys

import cv2
import numpy as np
from ultralytics import YOLO


ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data" / "tear_detection"
MODEL_PATH = (
    Path(sys.argv[1])
    if len(sys.argv) > 1
    else ROOT_DIR / "models" / "tear_detector.pt"
)
PREVIEW_PATH = ROOT_DIR / "reports" / "tear_detector_results.jpg"
THRESHOLDS = (0.001, 0.005, 0.01, 0.025, 0.05, 0.10, 0.25)


def beklenen_kutular(label_file: Path, width: int, height: int) -> list[tuple[float, ...]]:
    boxes = []
    for row in label_file.read_text(encoding="utf-8").splitlines():
        _, center_x, center_y, box_width, box_height = map(float, row.split())
        boxes.append(
            (
                (center_x - box_width / 2) * width,
                (center_y - box_height / 2) * height,
                (center_x + box_width / 2) * width,
                (center_y + box_height / 2) * height,
            )
        )
    return boxes


def kesisim_orani(first: tuple[float, ...], second: tuple[float, ...]) -> float:
    left = max(first[0], second[0])
    top = max(first[1], second[1])
    right = min(first[2], second[2])
    bottom = min(first[3], second[3])
    overlap = max(0.0, right - left) * max(0.0, bottom - top)
    first_area = (first[2] - first[0]) * (first[3] - first[1])
    second_area = (second[2] - second[0]) * (second[3] - second[1])
    return overlap / max(first_area + second_area - overlap, 1e-9)


def eslesen_kutu_sayisi(expected_boxes, found_boxes) -> int:
    unused = set(range(len(found_boxes)))
    matched = 0
    for actual_box in expected_boxes:
        candidates = [
            (kesisim_orani(actual_box, found_boxes[index]), index)
            for index in unused
        ]
        best_ratio, best_index = max(candidates, default=(0.0, -1))
        if best_ratio >= 0.5:
            matched += 1
            unused.remove(best_index)
    return matched


def onizleme_ciz(file, result, expected_boxes, boxes, confidences) -> np.ndarray:
    """Gerçek ve tahmin edilen kutuları tek bir küçük önizlemeye çizer."""
    drawn_image = result.orig_img.copy()
    for left, top, right, bottom in expected_boxes:
        cv2.rectangle(
            drawn_image,
            (int(left), int(top)),
            (int(right), int(bottom)),
            (0, 255, 255),
            5,
        )
    for box, confidence in zip(boxes, confidences):
        if confidence < 0.25:
            continue
        left, top, right, bottom = map(int, box)
        cv2.rectangle(drawn_image, (left, top), (right, bottom), (0, 255, 0), 5)
        cv2.putText(
            drawn_image,
            f"yirtik {confidence:.2f}",
            (left, max(20, top - 8)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (0, 255, 0),
            2,
            cv2.LINE_AA,
        )
    drawn_image = cv2.resize(drawn_image, (480, 270), interpolation=cv2.INTER_AREA)
    cv2.putText(
        drawn_image,
        file.name[-34:],
        (8, 24),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.55,
        (0, 255, 255),
        2,
        cv2.LINE_AA,
    )
    return drawn_image


def onizlemeleri_kaydet(previews: list[np.ndarray]) -> None:
    """Önizlemeleri üç sütunlu bir sonuç görselinde birleştirir."""
    if previews:
        rows = []
        for index in range(0, len(previews), 3):
            row = previews[index:index + 3]
            while len(row) < 3:
                row.append(np.zeros_like(row[0]))
            rows.append(cv2.hconcat(row))
        encoded_ok, image_data = cv2.imencode(".jpg", cv2.vconcat(rows))
        if encoded_ok:
            PREVIEW_PATH.parent.mkdir(parents=True, exist_ok=True)
            image_data.tofile(PREVIEW_PATH)
            print(f"Önizleme: {PREVIEW_PATH}")


def ana_program() -> None:
    """Yırtık modelini farklı güven eşiklerinde veri setiyle karşılaştırır."""
    model = YOLO(MODEL_PATH)
    data_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else DATA_DIR
    images = sorted((data_dir / "images" / "val").glob("*.jpg"))
    results = model.predict(images, imgsz=640, conf=0.0001, verbose=False)

    totals = {
        threshold: {"dogru": 0, "yanlis": 0, "eksik": 0, "bos_karede_yanlis": 0}
        for threshold in THRESHOLDS
    }
    previews = []
    for file, result in zip(images, results):
        height, width = result.orig_shape
        label = data_dir / "labels" / "val" / f"{file.stem}.txt"
        expected_boxes = beklenen_kutular(label, width, height)
        boxes = result.boxes.xyxy.cpu().tolist()
        confidences = result.boxes.conf.cpu().tolist()

        for threshold in THRESHOLDS:
            found_boxes = [box for box, confidence in zip(boxes, confidences) if confidence >= threshold]
            matched = eslesen_kutu_sayisi(expected_boxes, found_boxes)
            totals[threshold]["dogru"] += matched
            totals[threshold]["yanlis"] += len(found_boxes) - matched
            totals[threshold]["eksik"] += len(expected_boxes) - matched
            if not expected_boxes and found_boxes:
                totals[threshold]["bos_karede_yanlis"] += 1

        if expected_boxes or any(confidence >= 0.25 for confidence in confidences):
            previews.append(onizleme_ciz(file, result, expected_boxes, boxes, confidences))

    print(f"Model: {MODEL_PATH}")
    print(f"Doğrulama: {len(images)} görüntü")
    for threshold, counts in totals.items():
        precision = counts["dogru"] / max(counts["dogru"] + counts["yanlis"], 1)
        recall = counts["dogru"] / max(counts["dogru"] + counts["eksik"], 1)
        print(
            f"eşik={threshold:.3f}: kesinlik={precision:.3f}, bulma={recall:.3f}, "
            f"doğru={counts['dogru']}, yanlış={counts['yanlis']}, "
            f"eksik={counts['eksik']}, boş-karede-yanlış={counts['bos_karede_yanlis']}/10"
        )

    onizlemeleri_kaydet(previews)


if __name__ == "__main__":
    ana_program()
