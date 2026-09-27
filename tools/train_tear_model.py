"""Kutulu yırtık veri setinden aday bir YOLO modeli eğitir."""

from pathlib import Path

from ultralytics import YOLO


ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT_DIR / "data" / "tear_detection" / "dataset.yaml"
TRAINING_DIR = ROOT_DIR / "runs"


def ana_program() -> None:
    """Etiketli yırtık verileriyle yeni bir aday YOLO modeli eğitir."""
    model = YOLO(ROOT_DIR / "models" / "yolo11n_base.pt")
    model.train(
        data=str(DATA_PATH),
        epochs=50,
        imgsz=640,
        batch=4,
        device="cpu",
        workers=0,
        project=str(TRAINING_DIR),
        name="tear_detector_candidate",
        exist_ok=True,
        patience=12,
        seed=45,
        deterministic=True,
        optimizer="AdamW",
        lr0=0.0005,
        lrf=0.05,
        cos_lr=True,
        warmup_epochs=1.0,
        weight_decay=0.0005,
        freeze=10,
        degrees=10.0,
        translate=0.10,
        scale=0.25,
        fliplr=0.5,
        flipud=0.05,
        hsv_h=0.01,
        hsv_s=0.25,
        hsv_v=0.25,
        mosaic=0.3,
        close_mosaic=8,
        cache=False,
        plots=True,
        verbose=True,
    )

    best_model = TRAINING_DIR / "tear_detector_candidate" / "weights" / "best.pt"
    print(f"Yeni yırtık model adayı: {best_model}")
    print("Canli uygulama modeli otomatik olarak degistirilmedi.")


if __name__ == "__main__":
    ana_program()
