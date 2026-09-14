"""Hazirlanan yirtik kutularini tek bir kontrol goruntusunde gosterir."""

from pathlib import Path

import cv2
import numpy as np


ANA_KLASOR = Path(__file__).resolve().parents[1]
VERI_KLASORU = ANA_KLASOR / "data" / "tear_detection"
CIKTI_YOLU = ANA_KLASOR / "reports" / "tear_label_preview.jpg"


def kutulari_oku(etiket_dosyasi: Path, genislik: int, yukseklik: int):
    for satir in etiket_dosyasi.read_text(encoding="utf-8").splitlines():
        _, orta_x, orta_y, kutu_genisligi, kutu_yuksekligi = map(float, satir.split())
        yield (
            int((orta_x - kutu_genisligi / 2) * genislik),
            int((orta_y - kutu_yuksekligi / 2) * yukseklik),
            int((orta_x + kutu_genisligi / 2) * genislik),
            int((orta_y + kutu_yuksekligi / 2) * yukseklik),
        )


def resmi_hazirla(dosya: Path) -> np.ndarray:
    kare = cv2.imdecode(np.fromfile(dosya, dtype=np.uint8), cv2.IMREAD_COLOR)
    yukseklik, genislik = kare.shape[:2]
    etiket = VERI_KLASORU / "labels" / dosya.parent.name / f"{dosya.stem}.txt"
    for sol, ust, sag, alt in kutulari_oku(etiket, genislik, yukseklik):
        cv2.rectangle(kare, (sol, ust), (sag, alt), (0, 255, 255), 8)
    cv2.putText(
        kare,
        dosya.name[-38:],
        (20, 45),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.0,
        (0, 255, 255),
        3,
        cv2.LINE_AA,
    )
    kare = cv2.resize(kare, (640, 360), interpolation=cv2.INTER_AREA)
    return kare


def ana_program() -> None:
    """Yırtık etiket kutularını resimlerin üzerine çizip önizleme oluşturur."""
    secilen_resimler = []
    for bolum in ("train", "val"):
        klasor = VERI_KLASORU / "images" / bolum
        yeni_resimler = sorted(klasor.glob("phone_pos_*.jpg"))
        eski_resimler = []
        for grup in ("K001", "K002", "K003", "K004"):
            bulunan = next(iter(sorted(klasor.glob(f"old_pos_*{grup}*_01.jpg"))), None)
            if bulunan:
                eski_resimler.append(bulunan)
        secilen_resimler.extend(eski_resimler + yeni_resimler)

    satirlar = []
    for sira in range(0, len(secilen_resimler), 2):
        satir = [resmi_hazirla(dosya) for dosya in secilen_resimler[sira:sira + 2]]
        if len(satir) == 1:
            satir.append(satir[0] * 0)
        satirlar.append(cv2.hconcat(satir))
    onizleme = cv2.vconcat(satirlar)
    CIKTI_YOLU.parent.mkdir(parents=True, exist_ok=True)
    kodlandi, resim_verisi = cv2.imencode(".jpg", onizleme)
    if not kodlandi:
        raise RuntimeError("Kontrol goruntusu kodlanamadi")
    resim_verisi.tofile(CIKTI_YOLU)
    print(CIKTI_YOLU)


if __name__ == "__main__":
    ana_program()
