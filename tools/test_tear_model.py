"""Yeni yırtık modelinin kutu sonuçlarını kontrol eder."""

from pathlib import Path
import sys

import cv2
import numpy as np
from ultralytics import YOLO


ANA_KLASOR = Path(__file__).resolve().parents[1]
VERI_KLASORU = ANA_KLASOR / "data" / "tear_detection"
MODEL_YOLU = (
    Path(sys.argv[1])
    if len(sys.argv) > 1
    else ANA_KLASOR / "models" / "tear_detector.pt"
)
ONIZLEME_YOLU = ANA_KLASOR / "reports" / "tear_detector_results.jpg"
ESIKLER = (0.001, 0.005, 0.01, 0.025, 0.05, 0.10, 0.25)


def beklenen_kutular(etiket_dosyasi: Path, genislik: int, yukseklik: int) -> list[tuple[float, ...]]:
    kutular = []
    for satir in etiket_dosyasi.read_text(encoding="utf-8").splitlines():
        _, orta_x, orta_y, kutu_genisligi, kutu_yuksekligi = map(float, satir.split())
        kutular.append(
            (
                (orta_x - kutu_genisligi / 2) * genislik,
                (orta_y - kutu_yuksekligi / 2) * yukseklik,
                (orta_x + kutu_genisligi / 2) * genislik,
                (orta_y + kutu_yuksekligi / 2) * yukseklik,
            )
        )
    return kutular


def kesisim_orani(birinci: tuple[float, ...], ikinci: tuple[float, ...]) -> float:
    sol = max(birinci[0], ikinci[0])
    ust = max(birinci[1], ikinci[1])
    sag = min(birinci[2], ikinci[2])
    alt = min(birinci[3], ikinci[3])
    kesisim = max(0.0, sag - sol) * max(0.0, alt - ust)
    birinci_alan = (birinci[2] - birinci[0]) * (birinci[3] - birinci[1])
    ikinci_alan = (ikinci[2] - ikinci[0]) * (ikinci[3] - ikinci[1])
    return kesisim / max(birinci_alan + ikinci_alan - kesisim, 1e-9)


def eslesen_kutu_sayisi(beklenenler, bulunanlar) -> int:
    kullanilmayanlar = set(range(len(bulunanlar)))
    eslesen = 0
    for gercek_kutu in beklenenler:
        adaylar = [
            (kesisim_orani(gercek_kutu, bulunanlar[sira]), sira)
            for sira in kullanilmayanlar
        ]
        en_iyi_oran, en_iyi_sira = max(adaylar, default=(0.0, -1))
        if en_iyi_oran >= 0.5:
            eslesen += 1
            kullanilmayanlar.remove(en_iyi_sira)
    return eslesen


def ana_program() -> None:
    """Yırtık modelini farklı güven eşiklerinde veri setiyle karşılaştırır."""
    model = YOLO(MODEL_YOLU)
    veri_klasoru = Path(sys.argv[2]) if len(sys.argv) > 2 else VERI_KLASORU
    resimler = sorted((veri_klasoru / "images" / "val").glob("*.jpg"))
    sonuclar = model.predict(resimler, imgsz=640, conf=0.0001, verbose=False)

    toplamlar = {
        esik: {"dogru": 0, "yanlis": 0, "eksik": 0, "bos_karede_yanlis": 0}
        for esik in ESIKLER
    }
    onizlemeler = []
    for dosya, sonuc in zip(resimler, sonuclar):
        yukseklik, genislik = sonuc.orig_shape
        etiket = veri_klasoru / "labels" / "val" / f"{dosya.stem}.txt"
        beklenenler = beklenen_kutular(etiket, genislik, yukseklik)
        kutular = sonuc.boxes.xyxy.cpu().tolist()
        guvenler = sonuc.boxes.conf.cpu().tolist()

        for esik in ESIKLER:
            bulunanlar = [kutu for kutu, guven in zip(kutular, guvenler) if guven >= esik]
            eslesen = eslesen_kutu_sayisi(beklenenler, bulunanlar)
            toplamlar[esik]["dogru"] += eslesen
            toplamlar[esik]["yanlis"] += len(bulunanlar) - eslesen
            toplamlar[esik]["eksik"] += len(beklenenler) - eslesen
            if not beklenenler and bulunanlar:
                toplamlar[esik]["bos_karede_yanlis"] += 1

        if beklenenler or any(guven >= 0.25 for guven in guvenler):
            cizilmis_resim = sonuc.orig_img.copy()
            for sol, ust, sag, alt in beklenenler:
                cv2.rectangle(
                    cizilmis_resim,
                    (int(sol), int(ust)),
                    (int(sag), int(alt)),
                    (0, 255, 255),
                    5,
                )
            for kutu, guven in zip(kutular, guvenler):
                if guven < 0.25:
                    continue
                sol, ust, sag, alt = map(int, kutu)
                cv2.rectangle(cizilmis_resim, (sol, ust), (sag, alt), (0, 255, 0), 5)
                cv2.putText(
                    cizilmis_resim,
                    f"yirtik {guven:.2f}",
                    (sol, max(20, ust - 8)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (0, 255, 0),
                    2,
                    cv2.LINE_AA,
                )
            cizilmis_resim = cv2.resize(cizilmis_resim, (480, 270), interpolation=cv2.INTER_AREA)
            cv2.putText(
                cizilmis_resim,
                dosya.name[-34:],
                (8, 24),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                (0, 255, 255),
                2,
                cv2.LINE_AA,
            )
            onizlemeler.append(cizilmis_resim)

    print(f"Model: {MODEL_YOLU}")
    print(f"Doğrulama: {len(resimler)} görüntü")
    for esik, sayilar in toplamlar.items():
        kesinlik = sayilar["dogru"] / max(sayilar["dogru"] + sayilar["yanlis"], 1)
        bulma_orani = sayilar["dogru"] / max(sayilar["dogru"] + sayilar["eksik"], 1)
        print(
            f"eşik={esik:.3f}: kesinlik={kesinlik:.3f}, bulma={bulma_orani:.3f}, "
            f"doğru={sayilar['dogru']}, yanlış={sayilar['yanlis']}, "
            f"eksik={sayilar['eksik']}, boş-karede-yanlış={sayilar['bos_karede_yanlis']}/10"
        )

    if onizlemeler:
        satirlar = []
        for sira in range(0, len(onizlemeler), 3):
            satir = onizlemeler[sira:sira + 3]
            while len(satir) < 3:
                satir.append(np.zeros_like(satir[0]))
            satirlar.append(cv2.hconcat(satir))
        kodlandi, resim_verisi = cv2.imencode(".jpg", cv2.vconcat(satirlar))
        if kodlandi:
            ONIZLEME_YOLU.parent.mkdir(parents=True, exist_ok=True)
            resim_verisi.tofile(ONIZLEME_YOLU)
            print(f"Önizleme: {ONIZLEME_YOLU}")


if __name__ == "__main__":
    ana_program()
