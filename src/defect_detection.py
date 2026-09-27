"""Kamera görüntüsündeki leke ve yırtıkları kontrol eder."""

from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
from ultralytics import YOLO

from .config import (
    LIGHT_FABRIC_BRIGHTNESS_LIMIT,
    LIGHT_STAIN_MAX_AREA,
    LIGHT_STAIN_MIN_AREA,
    LIGHT_STAIN_BRIGHTNESS_DIFF,
    LIGHT_STAIN_COLOR_DIFF,
    COMBINED_STAIN_THRESHOLD,
    PORTRAIT_IMAGE_RATIO,
    STAIN_THRESHOLD,
    STAIN_IMAGE_SIZE,
    STAIN_MODEL_PATH,
    TEAR_CANDIDATE_THRESHOLD,
    TEAR_IMAGE_SIZE,
    STRONG_TEAR_THRESHOLD,
    TEAR_CHECK_SIZES,
    TEAR_CHECK_THRESHOLD,
    TEAR_CHECK_MODEL_PATH,
    TEAR_MODEL_PATH,
)


@dataclass(frozen=True)
class YirtikKutusu:
    """Yırtık kutusunun dört kenarını ve modelin güven puanını saklar."""

    left: int
    top: int
    right: int
    bottom: int
    confidence: float


@dataclass(frozen=True)
class GoruntuSonucu:
    """Kamera karesi bittikten sonra arayüze gönderilecek sonuçları saklar."""

    stain_score: float
    tear_score: float
    has_stain: bool
    has_tear: bool
    tear_boxes: tuple[YirtikKutusu, ...] = ()
    tear_check_score: float = 0.0
    tear_checked: bool = False


class KusurTespiti:
    """Leke ve yırtık modellerini çalıştırıp tek bir sonuç hazırlar."""

    def __init__(
        self,
        stain_model_path: Path = STAIN_MODEL_PATH,
        tear_model_path: Path = TEAR_MODEL_PATH,
        tear_check_model_path: Path = TEAR_CHECK_MODEL_PATH,
    ) -> None:
        # Üç modelin görevleri farklıdır:
        # leke modeli tüm kareyi, yırtık modeli konumu, kontrol modeli doğruluğu inceler.
        self.stain_model = YOLO(stain_model_path)
        self.tear_model = YOLO(tear_model_path)
        self.tear_check_model = YOLO(tear_check_model_path)

    @staticmethod
    def _sinif_puani(result, class_name: str) -> float:
        """YOLO sonucundan istediğim sınıfın 0 ile 1 arasındaki puanını alır."""
        index = next(int(i) for i, name in result.names.items() if name == class_name)
        return float(result.probs.data[index].item())

    def _farkli_boyutlarda_puan(
        self,
        model,
        frame: np.ndarray,
        class_name: str,
        sizes: tuple[int, ...],
    ) -> float:
        """Aynı resmi farklı boyutlarda deneyip en yüksek puanı kullanır."""

        # Küçük yırtık bazen büyük görüntü boyutunda daha net bulunabiliyor.
        scores = (
            self._sinif_puani(
                model.predict(
                    frame,
                    imgsz=size,
                    verbose=False,
                )[0],
                class_name,
            )
            for size in sizes
        )
        return max(scores)

    @staticmethod
    def _yirtik_kutulari(result) -> tuple[YirtikKutusu, ...]:
        """YOLO'nun verdiği koordinatları daha kolay kullanacağım kutulara çevirir."""
        coordinates = result.boxes.xyxy.cpu().tolist()
        confidences = result.boxes.conf.cpu().tolist()
        return tuple(
            YirtikKutusu(
                left=max(0, int(round(left))),
                top=max(0, int(round(top))),
                right=max(0, int(round(right))),
                bottom=max(0, int(round(bottom))),
                confidence=float(confidence),
            )
            for (left, top, right, bottom), confidence in zip(coordinates, confidences)
        )

    @staticmethod
    def _yirtik_var_mi(
        boxes: tuple[YirtikKutusu, ...], check_score: float
    ) -> bool:
        """Kutu ve kontrol puanlarına bakıp son yırtık kararını verir."""

        # Önce mutlaka bir yırtık kutusu bulunmalı. Sonra iki puandan biri yeterlidir.
        if not boxes:
            return False
        best_box = max(box.confidence for box in boxes)
        return (
            best_box >= STRONG_TEAR_THRESHOLD
            or check_score >= TEAR_CHECK_THRESHOLD
        )

    @staticmethod
    def _leke_var_mi(score: float, has_tear: bool) -> bool:
        """Leke puanını uygun sınırla karşılaştırır."""

        # Yırtık alanı kapatıldığı için birleşik görüntüde daha düşük sınır kullanılıyor.
        threshold = COMBINED_STAIN_THRESHOLD if has_tear else STAIN_THRESHOLD
        return score >= threshold

    def _leke_puani(self, frame: np.ndarray) -> float:
        """Kareyi leke modeline gönderip leke puanını alır."""

        # Kamera görüntüsü dikeyse leke küçük kalabiliyor. Bu yüzden orta kareyi de
        # ayrıca kontrol edip iki sonuçtan yüksek olanı seçiyorum.
        height, width = frame.shape[:2]
        images = [frame]
        ratio = max(height, width) / max(1, min(height, width))
        if height > width and ratio >= PORTRAIT_IMAGE_RATIO:
            edge = min(height, width)
            start = (height - edge) // 2
            images.append(frame[start:start + edge, :])

        results = self.stain_model.predict(
            images,
            imgsz=STAIN_IMAGE_SIZE,
            verbose=False,
        )
        return max(self._sinif_puani(result, "leke") for result in results)

    @staticmethod
    def _yirtiklari_kapat(
        frame: np.ndarray,
        boxes: tuple[YirtikKutusu, ...],
    ) -> np.ndarray:
        """Yırtık bölgelerini geçici olarak doldurup leke modelinden gizler."""
        if not boxes:
            return frame
        height, width = frame.shape[:2]
        mask = np.zeros((height, width), dtype=np.uint8)
        for box in boxes:
            box_width = max(1, box.right - box.left)
            box_height = max(1, box.bottom - box.top)
            margin = max(8, round(max(box_width, box_height) * 0.25))
            left = max(0, box.left - margin)
            top = max(0, box.top - margin)
            right = min(width - 1, box.right + margin)
            bottom = min(height - 1, box.bottom + margin)
            cv2.rectangle(mask, (left, top), (right, bottom), 255, -1)
        # inpaint, kutunun içini çevresindeki kumaş renklerine benzeterek doldurur.
        return cv2.inpaint(frame, mask, 5, cv2.INPAINT_TELEA)

    @staticmethod
    def _acik_kumasta_leke_puani(frame: np.ndarray) -> float:
        """Modelin kaçırabildiği açık krem kumaştaki silik lekeleri ayrıca arar."""
        height, width = frame.shape[:2]
        scale = min(1.0, 640.0 / max(height, width))
        if scale < 1.0:
            image = cv2.resize(
                frame,
                (round(width * scale), round(height * scale)),
                interpolation=cv2.INTER_AREA,
            )
        else:
            image = frame

        # LAB renk uzayında parlaklık ve renk farklarını ayrı ayrı ölçmek daha kolaydır.
        lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB).astype(np.float32)
        center_area = lab[
            round(lab.shape[0] * 0.05):round(lab.shape[0] * 0.95),
            round(lab.shape[1] * 0.05):round(lab.shape[1] * 0.95),
        ]
        center_light, center_a, center_b = np.median(center_area.reshape(-1, 3), axis=0)
        if center_light < LIGHT_FABRIC_BRIGHTNESS_LIMIT:
            return 0.0

        brightness_diff = center_light - lab[:, :, 0]
        color_diff = np.hypot(lab[:, :, 1] - center_a, lab[:, :, 2] - center_b)
        candidates = (
            (brightness_diff >= LIGHT_STAIN_BRIGHTNESS_DIFF)
            & (color_diff >= LIGHT_STAIN_COLOR_DIFF)
        ).astype(np.uint8) * 255

        edge_y = round(candidates.shape[0] * 0.04)
        edge_x = round(candidates.shape[1] * 0.04)
        candidates[:edge_y] = 0
        candidates[-edge_y:] = 0
        candidates[:, :edge_x] = 0
        candidates[:, -edge_x:] = 0
        # Küçük görüntü gürültülerini silip gerçek leke parçalarını birleştiriyorum.
        candidates = cv2.morphologyEx(
            candidates, cv2.MORPH_OPEN, np.ones((5, 5), dtype=np.uint8)
        )
        candidates = cv2.morphologyEx(
            candidates, cv2.MORPH_CLOSE, np.ones((9, 9), dtype=np.uint8)
        )

        return KusurTespiti._leke_bolgelerini_puanla(candidates, color_diff)

    @staticmethod
    def _leke_bolgelerini_puanla(
        candidates: np.ndarray, color_diff: np.ndarray
    ) -> float:
        """Uygun büyüklükte ve doluluktaki leke adayının puanını hesaplar."""
        image_area = candidates.shape[0] * candidates.shape[1]
        part_count, labels, stats, _centers = cv2.connectedComponentsWithStats(
            candidates
        )
        # Çok küçük, çok büyük veya uzun çizgi şeklindeki bölgeleri leke saymıyorum.
        for index in range(1, part_count):
            _x, _y, part_width, part_height, area = stats[index]
            area_ratio = area / image_area
            if not LIGHT_STAIN_MIN_AREA <= area_ratio <= LIGHT_STAIN_MAX_AREA:
                continue
            ratio = max(part_width, part_height) / max(
                1, min(part_width, part_height)
            )
            fill = area / max(1, part_width * part_height)
            if ratio <= 4.0 and fill >= 0.18:
                strength = float(np.percentile(color_diff[labels == index], 75))
                return min(0.90, 0.60 + max(0.0, strength - 7.0) * 0.02)
        return 0.0

    def hazirla(self) -> None:
        """Boş bir kare çalıştırıp modelleri canlı testten önce hazır hale getirir."""
        sample_frame = np.full((1280, 720, 3), 127, dtype=np.uint8)
        self.kontrol_et(sample_frame)

    def kontrol_et(self, frame: np.ndarray) -> GoruntuSonucu:
        """Bir kamera karesini baştan sona kontrol edip sonucu döndürür."""

        # Önce YOLO yırtığın konumunu bulur. İkinci model şüpheli sonucu doğrular.
        tear_result = self.tear_model.predict(
            frame,
            imgsz=TEAR_IMAGE_SIZE,
            conf=TEAR_CANDIDATE_THRESHOLD,
            max_det=10,
            verbose=False,
        )[0]
        candidate_boxes = self._yirtik_kutulari(tear_result)
        tear_score = max((box.confidence for box in candidate_boxes), default=0.0)

        # Kutu yoksa yırtık zaten kabul edilmiyor. Kutu çok güçlüyse de YOLO sonucu
        # yeterli oluyor. Yavaş olan ikinci modeli sadece şüpheli kutularda çalıştırıyorum.
        check_score = 0.0
        check_done = False
        if candidate_boxes and tear_score < STRONG_TEAR_THRESHOLD:
            check_done = True
            check_score = self._farkli_boyutlarda_puan(
                self.tear_check_model,
                frame,
                "yirtik",
                TEAR_CHECK_SIZES,
            )
        has_tear = self._yirtik_var_mi(candidate_boxes, check_score)
        tear_boxes = candidate_boxes if has_tear else ()

        # Yırtık deliği leke sanılmasın diye bu alan leke analizinden önce kapatılır.
        clean_frame = self._yirtiklari_kapat(frame, tear_boxes)
        model_stain_score = self._leke_puani(clean_frame)
        light_stain_score = self._acik_kumasta_leke_puani(clean_frame)
        stain_score = max(model_stain_score, light_stain_score)
        has_stain = self._leke_var_mi(stain_score, has_tear)

        return GoruntuSonucu(
            stain_score=stain_score,
            tear_score=tear_score,
            has_stain=has_stain,
            has_tear=has_tear,
            tear_boxes=tear_boxes,
            tear_check_score=check_score,
            tear_checked=check_done,
        )
