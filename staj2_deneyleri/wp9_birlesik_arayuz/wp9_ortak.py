"""WP9 ortak karar motoru: dondurulmus leke + yeni yirtik siniflandirma."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

from ultralytics import YOLO


LEKE_ESIGI = 0.58
YIRTIK_ESIGI = 0.50
GEREKLI_OY = 2


@dataclass
class KareSonucu:
    dosya: str
    leke_skoru: float
    yirtik_skoru: float
    leke: bool
    yirtik: bool


class KusurMotoru:
    def __init__(self, kok: Path | None = None) -> None:
        self.kok = kok or Path(__file__).resolve().parent
        self.leke_modeli = YOLO(self.kok / "modeller" / "leke_best_nihai.pt")
        self.yirtik_modeli = YOLO(self.kok / "modeller" / "yirtik_best_wp9.pt")

    @staticmethod
    def _sinif_skoru(sonuc, sinif_adi: str) -> float:
        indeks = next(int(i) for i, ad in sonuc.names.items() if ad == sinif_adi)
        return float(sonuc.probs.data[indeks].item())

    def kareyi_incele(self, dosya: Path) -> KareSonucu:
        leke = self.leke_modeli.predict(str(dosya), imgsz=640, verbose=False)[0]
        yirtik = self.yirtik_modeli.predict(str(dosya), imgsz=224, verbose=False)[0]
        leke_skoru = self._sinif_skoru(leke, "leke")
        yirtik_skoru = self._sinif_skoru(yirtik, "yirtik")
        return KareSonucu(
            dosya=str(dosya),
            leke_skoru=leke_skoru,
            yirtik_skoru=yirtik_skoru,
            leke=leke_skoru >= LEKE_ESIGI,
            yirtik=yirtik_skoru >= YIRTIK_ESIGI,
        )

    def uclu_incele(self, dosyalar: list[Path]) -> dict:
        if len(dosyalar) != 3:
            raise ValueError("Guvenli saha karari icin tam 3 RGB kare gereklidir.")
        kareler = [self.kareyi_incele(x) for x in dosyalar]
        leke_oyu = sum(x.leke for x in kareler)
        yirtik_oyu = sum(x.yirtik for x in kareler)
        leke_var = leke_oyu >= GEREKLI_OY
        yirtik_var = yirtik_oyu >= GEREKLI_OY
        if leke_var and yirtik_var:
            karar = "LEKE+YIRTIK"
        elif leke_var:
            karar = "LEKE"
        elif yirtik_var:
            karar = "YIRTIK"
        else:
            karar = "NORMAL"
        return {
            "zaman": datetime.now().astimezone().isoformat(),
            "karar": karar,
            "leke_var": leke_var,
            "yirtik_var": yirtik_var,
            "leke_oyu": leke_oyu,
            "yirtik_oyu": yirtik_oyu,
            "leke_esigi": LEKE_ESIGI,
            "yirtik_esigi": YIRTIK_ESIGI,
            "kareler": [asdict(x) for x in kareler],
        }


def json_kaydet(sonuc: dict, hedef: Path) -> None:
    hedef.parent.mkdir(parents=True, exist_ok=True)
    hedef.write_text(json.dumps(sonuc, ensure_ascii=False, indent=2), encoding="utf-8")
