"""Leke ve yirtik kararini kayitli kamera karelerinde sinar."""

from pathlib import Path
import sys

import cv2
import numpy as np


ANA_KLASOR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ANA_KLASOR))

from src.defect_detection import KusurTespiti  # noqa: E402


def resmi_oku(dosya: Path) -> np.ndarray | None:
    kodlanmis_resim = np.fromfile(dosya, dtype=np.uint8)
    if kodlanmis_resim.size == 0:
        return None
    return cv2.imdecode(kodlanmis_resim, cv2.IMREAD_COLOR)


def ana_program() -> None:
    """Kaydedilmiş görüntüleri çalıştırıp beklenen ve bulunan sonuçları yazar."""
    kusur_tespiti = KusurTespiti()
    kusur_tespiti.hazirla()
    kayit_klasoru = ANA_KLASOR / "data" / "raw"
    beklenen_sonuclar = {
        "normal": (False, False),
        "stain": (True, False),
        "tear": (False, True),
        "combined": (True, True),
    }
    dogru_yirtik = 0
    dogru_leke = 0
    toplam = 0

    print("grup     | karar        | leke | kutu/kontrol | adet | dosya")
    for grup, (leke_bekleniyor, yirtik_bekleniyor) in beklenen_sonuclar.items():
        for dosya in sorted((kayit_klasoru / grup).glob("*.jpg")):
            kare = resmi_oku(dosya)
            if kare is None:
                print(f"Atlandı (okunamadı): {dosya.name}")
                continue
            sonuc = kusur_tespiti.kontrol_et(kare)
            toplam += 1
            dogru_yirtik += sonuc.yirtik_var == yirtik_bekleniyor
            dogru_leke += sonuc.leke_var == leke_bekleniyor
            if sonuc.leke_var and sonuc.yirtik_var:
                karar = "LEKE+YIRTIK"
            elif sonuc.yirtik_var:
                karar = "YIRTIK"
            elif sonuc.leke_var:
                karar = "LEKE"
            else:
                karar = "NORMAL"
            kontrol = (
                f"{sonuc.yirtik_kontrol_puani:4.2f}"
                if sonuc.yirtik_kontrol_yapildi
                else "  --"
            )
            print(
                f"{grup:8} | {karar:12} | {sonuc.leke_puani:4.2f} "
                f"| {sonuc.yirtik_puani:4.2f}/{kontrol} "
                f"| {len(sonuc.yirtik_kutulari):4} | {dosya.name}"
            )

    print(f"\nYırtık ayrımı: {dogru_yirtik}/{toplam}")
    print(f"Leke ayrımı:   {dogru_leke}/{toplam}")


if __name__ == "__main__":
    ana_program()
