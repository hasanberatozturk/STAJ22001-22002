"""Leke ve yırtık kodunun basit kontrolleri."""

import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.config import STAIN_THRESHOLD
from src.defect_detection import KusurTespiti, YirtikKutusu


def dogrula(condition: bool, error_message: str) -> None:
    """Sonuç yanlışsa testi durdurup nedeni gösterir."""
    if not condition:
        raise RuntimeError(error_message)


class SahteSayi:
    def __init__(self, value: float) -> None:
        self.value = value

    def item(self) -> float:
        return self.value


class SahteVeri:
    def __init__(self, values: list[float]) -> None:
        self.values = values

    def __getitem__(self, index: int) -> SahteSayi:
        return SahteSayi(self.values[index])


class SahteSonuc:
    names = {0: "normal", 1: "yirtik"}

    def __init__(self, tear_score: float) -> None:
        self.probs = type(
            "Puanlar",
            (),
            {"data": SahteVeri([1.0 - tear_score, tear_score])},
        )()


class SahteModel:
    def __init__(self, scores: dict[int, float]) -> None:
        self.scores = scores
        self.used_sizes: list[int] = []

    def predict(self, _frame, *, imgsz: int, verbose: bool):
        if verbose:
            raise RuntimeError("Test sırasında ayrıntılı model çıktısı kapalı olmalı")
        self.used_sizes.append(imgsz)
        return [SahteSonuc(self.scores[imgsz])]


class SahteLekeSonucu:
    names = {0: "normal", 1: "leke"}

    def __init__(self, stain_score: float) -> None:
        self.probs = type(
            "Puanlar", (), {"data": SahteVeri([1.0 - stain_score, stain_score])}
        )()


class SahteLekeModeli:
    def __init__(self) -> None:
        self.image_count = 0

    def predict(self, images, *, imgsz: int, verbose: bool):
        if imgsz != 384 or verbose:
            raise RuntimeError("Leke modeli yanlış ayarla çağrıldı")
        self.image_count = len(images)
        scores = (0.05, 0.82) if len(images) == 2 else (0.05,)
        return [SahteLekeSonucu(score) for score in scores]


def farkli_boyut_kontrolu() -> None:
    detector = object.__new__(KusurTespiti)
    model = SahteModel({224: 0.19, 320: 0.99})

    score = detector._farkli_boyutlarda_puan(model, object(), "yirtik", (224, 320))

    dogrula(score == 0.99, "İki boyuttan yüksek olan puan seçilmedi")
    dogrula(
        model.used_sizes == [224, 320],
        "Model iki görüntü boyutuyla çalıştırılmadı",
    )


def yirtik_karari_kontrolu() -> None:
    weak_box = (YirtikKutusu(10, 20, 40, 60, 0.22),)
    strong_box = (YirtikKutusu(10, 20, 40, 60, 0.72),)

    dogrula(KusurTespiti._yirtik_var_mi(weak_box, 0.91), "Kontrol modeli dikkate alınmadı")
    dogrula(KusurTespiti._yirtik_var_mi(strong_box, 0.05), "Güçlü kutu kabul edilmedi")
    dogrula(not KusurTespiti._yirtik_var_mi(weak_box, 0.10), "Zayıf sonuç kabul edildi")
    dogrula(not KusurTespiti._yirtik_var_mi((), 0.99), "Kutusuz sonuç yırtık sayıldı")


def birlikte_leke_kontrolu() -> None:
    dogrula(not KusurTespiti._leke_var_mi(0.30, False), "Normal eşik yanlış çalıştı")
    dogrula(KusurTespiti._leke_var_mi(0.30, True), "Birleşik sonuç eşiği çalışmadı")
    dogrula(not KusurTespiti._leke_var_mi(0.11, True), "Çok düşük leke puanı kabul edildi")


def dikey_goruntu_kontrolu() -> None:
    detector = object.__new__(KusurTespiti)
    detector.stain_model = SahteLekeModeli()
    portrait_frame = np.zeros((1280, 720, 3), dtype=np.uint8)

    score = detector._leke_puani(portrait_frame)

    dogrula(detector.stain_model.image_count == 2, "Dikey görüntünün orta kısmı alınmadı")
    dogrula(score == 0.82, "Dikey görüntüde yüksek leke puanı seçilmedi")


def acik_leke_kontrolu() -> None:
    cream_fabric = np.full((480, 640, 3), (175, 195, 215), dtype=np.uint8)
    stained_fabric = cream_fabric.copy()
    cv2.ellipse(stained_fabric, (330, 250), (55, 30), 12, 0, 360, (105, 145, 180), -1)

    dogrula(
        KusurTespiti._acik_kumasta_leke_puani(cream_fabric) == 0.0,
        "Temiz krem kumaş lekeli sayıldı",
    )
    dogrula(
        KusurTespiti._acik_kumasta_leke_puani(stained_fabric) >= STAIN_THRESHOLD,
        "Krem kumaştaki açık leke bulunamadı",
    )


def yirtik_kapatma_kontrolu() -> None:
    frame = np.full((240, 320, 3), 180, dtype=np.uint8)
    frame[90:130, 130:175] = 0
    box = YirtikKutusu(130, 90, 175, 130, 0.9)

    clean_frame = KusurTespiti._yirtiklari_kapat(frame, (box,))

    dogrula(
        float(clean_frame[100:120, 140:165].mean()) > 150.0,
        "Yırtık bölgesi leke kontrolünden çıkarılmadı",
    )


def ana_test() -> None:
    farkli_boyut_kontrolu()
    yirtik_karari_kontrolu()
    birlikte_leke_kontrolu()
    dikey_goruntu_kontrolu()
    acik_leke_kontrolu()
    yirtik_kapatma_kontrolu()
    print("Leke ve yırtık kontrolleri geçti.")


if __name__ == "__main__":
    ana_test()
