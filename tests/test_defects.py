"""Leke ve yırtık kodunun basit kontrolleri."""

import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.config import LEKE_ESIGI
from src.defect_detection import KusurTespiti, YirtikKutusu


def dogrula(kosul: bool, hata_mesaji: str) -> None:
    """Sonuç yanlışsa testi durdurup nedeni gösterir."""
    if not kosul:
        raise RuntimeError(hata_mesaji)


class SahteSayi:
    def __init__(self, deger: float) -> None:
        self.deger = deger

    def item(self) -> float:
        return self.deger


class SahteVeri:
    def __init__(self, degerler: list[float]) -> None:
        self.degerler = degerler

    def __getitem__(self, sira: int) -> SahteSayi:
        return SahteSayi(self.degerler[sira])


class SahteSonuc:
    names = {0: "normal", 1: "yirtik"}

    def __init__(self, yirtik_puani: float) -> None:
        self.probs = type(
            "Puanlar",
            (),
            {"data": SahteVeri([1.0 - yirtik_puani, yirtik_puani])},
        )()


class SahteModel:
    def __init__(self, puanlar: dict[int, float]) -> None:
        self.puanlar = puanlar
        self.kullanilan_boyutlar: list[int] = []

    def predict(self, _kare, *, imgsz: int, verbose: bool):
        if verbose:
            raise RuntimeError("Test sırasında ayrıntılı model çıktısı kapalı olmalı")
        self.kullanilan_boyutlar.append(imgsz)
        return [SahteSonuc(self.puanlar[imgsz])]


class SahteLekeSonucu:
    names = {0: "normal", 1: "leke"}

    def __init__(self, leke_puani: float) -> None:
        self.probs = type(
            "Puanlar", (), {"data": SahteVeri([1.0 - leke_puani, leke_puani])}
        )()


class SahteLekeModeli:
    def __init__(self) -> None:
        self.goruntu_sayisi = 0

    def predict(self, goruntuler, *, imgsz: int, verbose: bool):
        if imgsz != 384 or verbose:
            raise RuntimeError("Leke modeli yanlış ayarla çağrıldı")
        self.goruntu_sayisi = len(goruntuler)
        puanlar = (0.05, 0.82) if len(goruntuler) == 2 else (0.05,)
        return [SahteLekeSonucu(puan) for puan in puanlar]


def farkli_boyut_kontrolu() -> None:
    tespit = object.__new__(KusurTespiti)
    model = SahteModel({224: 0.19, 320: 0.99})

    puan = tespit._farkli_boyutlarda_puan(model, object(), "yirtik", (224, 320))

    dogrula(puan == 0.99, "İki boyuttan yüksek olan puan seçilmedi")
    dogrula(
        model.kullanilan_boyutlar == [224, 320],
        "Model iki görüntü boyutuyla çalıştırılmadı",
    )


def yirtik_karari_kontrolu() -> None:
    zayif_kutu = (YirtikKutusu(10, 20, 40, 60, 0.22),)
    guclu_kutu = (YirtikKutusu(10, 20, 40, 60, 0.72),)

    dogrula(KusurTespiti._yirtik_var_mi(zayif_kutu, 0.91), "Kontrol modeli dikkate alınmadı")
    dogrula(KusurTespiti._yirtik_var_mi(guclu_kutu, 0.05), "Güçlü kutu kabul edilmedi")
    dogrula(not KusurTespiti._yirtik_var_mi(zayif_kutu, 0.10), "Zayıf sonuç kabul edildi")
    dogrula(not KusurTespiti._yirtik_var_mi((), 0.99), "Kutusuz sonuç yırtık sayıldı")


def birlikte_leke_kontrolu() -> None:
    dogrula(not KusurTespiti._leke_var_mi(0.30, False), "Normal eşik yanlış çalıştı")
    dogrula(KusurTespiti._leke_var_mi(0.30, True), "Birleşik sonuç eşiği çalışmadı")
    dogrula(not KusurTespiti._leke_var_mi(0.11, True), "Çok düşük leke puanı kabul edildi")


def dikey_goruntu_kontrolu() -> None:
    tespit = object.__new__(KusurTespiti)
    tespit.leke_modeli = SahteLekeModeli()
    dikey_kare = np.zeros((1280, 720, 3), dtype=np.uint8)

    puan = tespit._leke_puani(dikey_kare)

    dogrula(tespit.leke_modeli.goruntu_sayisi == 2, "Dikey görüntünün orta kısmı alınmadı")
    dogrula(puan == 0.82, "Dikey görüntüde yüksek leke puanı seçilmedi")


def acik_leke_kontrolu() -> None:
    krem_kumas = np.full((480, 640, 3), (175, 195, 215), dtype=np.uint8)
    lekeli_kumas = krem_kumas.copy()
    cv2.ellipse(lekeli_kumas, (330, 250), (55, 30), 12, 0, 360, (105, 145, 180), -1)

    dogrula(
        KusurTespiti._acik_kumasta_leke_puani(krem_kumas) == 0.0,
        "Temiz krem kumaş lekeli sayıldı",
    )
    dogrula(
        KusurTespiti._acik_kumasta_leke_puani(lekeli_kumas) >= LEKE_ESIGI,
        "Krem kumaştaki açık leke bulunamadı",
    )


def yirtik_kapatma_kontrolu() -> None:
    kare = np.full((240, 320, 3), 180, dtype=np.uint8)
    kare[90:130, 130:175] = 0
    kutu = YirtikKutusu(130, 90, 175, 130, 0.9)

    temiz_kare = KusurTespiti._yirtiklari_kapat(kare, (kutu,))

    dogrula(
        float(temiz_kare[100:120, 140:165].mean()) > 150.0,
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
