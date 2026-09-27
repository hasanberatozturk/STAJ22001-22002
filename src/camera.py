"""Kamera kaynağı seçimi ve boş/tek renk kare kontrolü."""

import cv2
import numpy as np

from .config import FRAME_WIDTH, FRAME_HEIGHT, CAMERA_SOURCES, FRAME_RATE


def kare_gecerli_mi(frame: np.ndarray | None) -> bool:
    """Kameradan gerçekten kullanılabilir bir görüntü gelip gelmediğine bakar."""

    # Bazı sanal kameralar bağlı değilken boş, siyah veya yeşil kare verebiliyor.
    if frame is None or frame.size == 0:
        return False
    renk_degisimi = float(
        np.mean(np.std(frame.astype(np.float32), axis=(0, 1)))
    )
    return renk_degisimi >= 0.5


def kamera_ac() -> tuple[cv2.VideoCapture | None, str | None]:
    """Kamera listesini sırayla dener ve görüntü veren ilk kamerayı seçer."""
    backends = {"MSMF": cv2.CAP_MSMF, "DSHOW": cv2.CAP_DSHOW}
    for number, backend_name in CAMERA_SOURCES:
        camera = cv2.VideoCapture(number, backends[backend_name])
        if not camera.isOpened():
            camera.release()
            continue
        camera.set(cv2.CAP_PROP_FRAME_WIDTH, FRAME_WIDTH)
        camera.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_HEIGHT)
        camera.set(cv2.CAP_PROP_FPS, FRAME_RATE)
        # Destekleyen kameralarda eski karelerin birikmesini azaltır.
        camera.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        # Kameranın açılması yetmez; birkaç gerçek kare okuyabildiğini de kontrol ediyorum.
        for _ in range(6):
            read_ok, candidate_frame = camera.read()
            if read_ok and kare_gecerli_mi(candidate_frame):
                height, width = candidate_frame.shape[:2]
                return camera, f"{backend_name}/{number} • {width}x{height}"
        camera.release()
    return None, None
