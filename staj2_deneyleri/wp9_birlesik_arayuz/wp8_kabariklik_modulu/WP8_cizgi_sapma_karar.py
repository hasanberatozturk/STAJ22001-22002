"""WP8 nihai basit karar: lazer cizgisi belirgin saparsa KUSUR.

Kapsam:
- Duz yuzeyli acik, koyu, desenli ve parlak kumaslar.
- Belirgin kirisiklik ve kabariklik/sirt.
- Kat izi ve kendinden kirisik/dokulu kumaslar kapsam disidir.

Bu betik RF/SVM veya milimetre tahmini kullanmaz. Her kumasin duz
referanslarindan o kumasa ozel bir cizgi-sapma esigi kurar.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
from datetime import datetime
from pathlib import Path

import numpy as np


SURUM = "WP8-CIZGI-SAPMA-FINAL-R4-20260827"
MINIMUM_REFERANS = 3
MINIMUM_TEST = 3
GUVENLIK_CARPANI = 1.12
MINIMUM_GUVENLIK_MARJI_PX = 0.20
# Kalinlik olcutu kucuk farklara duyarlidir; nihai karar tek olcumle degil,
# en az iki ayri taramada tekrarlandiginda verilir. Bu nedenle kumasa ozel
# normal referans zarfina kucuk bir pay eklemek yeterlidir.
KALINLIK_GUVENLIK_CARPANI = 1.05
KALINLIK_MINIMUM_MARJI_PX = 0.005
MEDYAN_ZARF_ORANI = 0.20
MEDYAN_MINIMUM_MARJI_PX = 0.02
MINIMUM_LAZER_GUCU = 10.0


def modulu_yukle(betik: Path):
    spec = importlib.util.spec_from_file_location("wp8_ortak", betik)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Ortak profil betigi yuklenemedi: {betik}")
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


ORTAK = modulu_yukle(Path(__file__).with_name("WP8_canli_tahmin.py"))

# Kameranin kenar bolgeleri yerine lazerin kullanisli orta bolgesi incelenir.
ANALIZ_BASLANGIC = ORTAK.ANALIZ_SOL - ORTAK.X0
ANALIZ_BITIS = ORTAK.ANALIZ_SAG - ORTAK.X0 + 1


def tek_cift_kalinlik(acik: Path, kapali: Path) -> np.ndarray:
    """Her sutunda lazer cizgisinin agirlikli kalinligini olcer."""
    acik_rgb = ORTAK.rgb_oku(acik)
    kapali_rgb = ORTAK.rgb_oku(kapali)
    fark = acik_rgb - kapali_rgb
    skor = fark[..., 0] - 0.55 * fark[..., 1] - 0.45 * fark[..., 2]
    roi = skor[ORTAK.Y0:ORTAK.Y1, ORTAK.X0:ORTAK.X1]
    yumusatilmis = (
        np.roll(roi, -2, axis=0)
        + 2 * np.roll(roi, -1, axis=0)
        + 3 * roi
        + 2 * np.roll(roi, 1, axis=0)
        + np.roll(roi, 2, axis=0)
    ) / 9.0
    tepeler = np.argmax(yumusatilmis, axis=0)
    kalinlik = np.empty(yumusatilmis.shape[1], dtype=float)
    for sutun, tepe in enumerate(tepeler):
        alt = max(0, tepe - 10)
        ust = min(yumusatilmis.shape[0], tepe + 11)
        degerler = yumusatilmis[alt:ust, sutun]
        taban = np.percentile(yumusatilmis[:, sutun], 65)
        agirlik = np.clip(degerler - taban, 0, None)
        if agirlik.sum() <= 1e-6:
            kalinlik[sutun] = np.nan
            continue
        y = np.arange(alt, ust, dtype=float)
        merkez = float(np.sum(y * agirlik) / agirlik.sum())
        kalinlik[sutun] = math.sqrt(
            float(np.sum(((y - merkez) ** 2) * agirlik) / agirlik.sum())
        )
    return kalinlik


def profil_oku(klasor: Path, onek: str) -> tuple[np.ndarray, float, np.ndarray]:
    acik = sorted(klasor.glob(f"{onek}_A_*.jpg"))
    kapali = sorted(klasor.glob(f"{onek}_K_*.jpg"))
    if len(acik) != 3 or len(kapali) != 3:
        raise FileNotFoundError(
            f"{klasor / onek}: 3 lazer acik ve 3 lazer kapali goruntu gerekli."
        )
    profil, guc = ORTAK.goruntu_ciftlerini_isle(acik, kapali)
    kalinliklar = [tek_cift_kalinlik(a, k) for a, k in zip(acik, kapali)]
    kalinlik = np.nanmedian(np.stack(kalinliklar), axis=0)
    return np.asarray(profil, dtype=float), float(np.median(guc)), kalinlik


def onekleri_bul(klasor: Path, kok: str) -> list[str]:
    onekler = sorted(
        {dosya.name.rsplit("_A_", 1)[0] for dosya in klasor.glob(f"{kok}_*_A_01.jpg")}
    )
    return onekler


def dogrudan_sapma_araligi(profil: np.ndarray) -> float:
    """Cizginin dogruya gore saglam (yuzde 1-99) sapma araligini verir."""
    y = profil[ANALIZ_BASLANGIC:ANALIZ_BITIS]
    x = np.arange(len(y), dtype=float)
    dogru = np.polyval(np.polyfit(x, y, 1), x)
    artik = y - dogru
    return float(np.percentile(artik, 99) - np.percentile(artik, 1))


def kalinlik_anomalisi(kalinlik: np.ndarray) -> float:
    """Cizginin yerel kalinlasma/incelme miktarinin p95 degerini verir."""
    deger = kalinlik[ANALIZ_BASLANGIC:ANALIZ_BITIS]
    pencere = 81
    yarim = pencere // 2
    dolgulu = np.pad(deger, (yarim, yarim), mode="reflect")
    yerel_taban = np.convolve(
        dolgulu, np.ones(pencere, dtype=float) / pencere, mode="valid"
    )
    return float(np.percentile(np.abs(deger - yerel_taban), 95))


def profil_medyan_y(profil: np.ndarray) -> float:
    """Orta bolgenin yan referans dogrusuna gore toplu konumunu verir."""
    return float(np.median(profil[ANALIZ_BASLANGIC:ANALIZ_BITIS]))


def seriyi_oku(klasor: Path, kok: str, minimum: int) -> list[dict]:
    onekler = onekleri_bul(klasor, kok)
    if len(onekler) < minimum:
        raise ValueError(
            f"{klasor}: en az {minimum} olcum gerekli; bulunan {len(onekler)}."
        )
    kayitlar = []
    for onek in onekler:
        profil, guc, kalinlik = profil_oku(klasor, onek)
        if guc < MINIMUM_LAZER_GUCU:
            raise ValueError(
                f"{onek}: lazer sinyali cok zayif ({guc:.1f}). Olcumu tekrarlayin."
            )
        kayitlar.append(
            {
                "onek": onek,
                "sapma_araligi_px": dogrudan_sapma_araligi(profil),
                "kalinlik_anomalisi_px": kalinlik_anomalisi(kalinlik),
                "profil_medyan_y_px": profil_medyan_y(profil),
                "lazer_gucu": guc,
            }
        )
    return kayitlar


def esik_kur(normal_kayitlari: list[dict]) -> tuple[float, float]:
    en_kotu_normal = max(k["sapma_araligi_px"] for k in normal_kayitlari)
    sapma_esigi = max(
        en_kotu_normal * GUVENLIK_CARPANI,
        en_kotu_normal + MINIMUM_GUVENLIK_MARJI_PX,
    )
    en_kotu_kalinlik = max(k["kalinlik_anomalisi_px"] for k in normal_kayitlari)
    kalinlik_esigi = max(
        en_kotu_kalinlik * KALINLIK_GUVENLIK_CARPANI,
        en_kotu_kalinlik + KALINLIK_MINIMUM_MARJI_PX,
    )
    return sapma_esigi, kalinlik_esigi


def medyan_zarfi_kur(normal_kayitlari: list[dict]) -> tuple[float, float]:
    """Duz referanslarin toplu cizgi konumu icin alt/ust sinir kurar."""
    degerler = [k["profil_medyan_y_px"] for k in normal_kayitlari]
    alt = min(degerler)
    ust = max(degerler)
    marj = max((ust - alt) * MEDYAN_ZARF_ORANI, MEDYAN_MINIMUM_MARJI_PX)
    return alt - marj, ust + marj


def degerlendir(normal_kayitlari: list[dict], test_kayitlari: list[dict]) -> dict:
    sapma_esigi, kalinlik_esigi = esik_kur(normal_kayitlari)
    medyan_alt_esigi, medyan_ust_esigi = medyan_zarfi_kur(normal_kayitlari)
    gerekli_kanit = max(2, math.ceil(len(test_kayitlari) * 0.40))
    for kayit in test_kayitlari:
        kayit["merkez_sapmasi_var"] = kayit["sapma_araligi_px"] >= sapma_esigi
        kayit["kalinlik_sapmasi_var"] = (
            kayit["kalinlik_anomalisi_px"] >= kalinlik_esigi
        )
        kayit["toplu_kayma_var"] = not (
            medyan_alt_esigi
            <= kayit["profil_medyan_y_px"]
            <= medyan_ust_esigi
        )
        # Toplu konum, kumasin kamera altinda cok az yer degistirmesinden veya
        # duzlemin egiminden de etkilenebilir. Bu nedenle toplu kayma tek
        # basina kabariklik kaniti sayilmaz; ekranda tani bilgisi olarak
        # tutulur. Kusur karari lazer cizgisinin sekil ya da kalinlik
        # bozulmasinin ayri taramalarda tekrarlanmasina dayanir.
        kayit["esik_asildi"] = (
            kayit["merkez_sapmasi_var"] or kayit["kalinlik_sapmasi_var"]
        )
    kanit = sum(int(k["esik_asildi"]) for k in test_kayitlari)
    kusur = kanit >= gerekli_kanit
    return {
        "surum": SURUM,
        "zaman": datetime.now().astimezone().isoformat(),
        "tahmin": "KUSUR" if kusur else "NORMAL",
        "gerekce": (
            "Lazer cizgisinde tekrarlanan belirgin sapma bulundu."
            if kusur
            else "Lazer cizgisi kumasin duz referans sinirlari icinde kaldi."
        ),
        "sapma_esigi_px": sapma_esigi,
        "kalinlik_anomalisi_esigi_px": kalinlik_esigi,
        "profil_medyan_alt_esigi_px": medyan_alt_esigi,
        "profil_medyan_ust_esigi_px": medyan_ust_esigi,
        "gerekli_kanit": gerekli_kanit,
        "bulunan_kanit": kanit,
        "normal_referanslar": normal_kayitlari,
        "test_olcumleri": test_kayitlari,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--normal", type=Path, required=True)
    parser.add_argument("--test", type=Path, required=True)
    parser.add_argument("--normal-onek", default="normal")
    parser.add_argument("--test-onek", default="konum")
    parser.add_argument("--cikti", type=Path, required=True)
    args = parser.parse_args()

    normaller = seriyi_oku(args.normal, args.normal_onek, MINIMUM_REFERANS)
    testler = seriyi_oku(args.test, args.test_onek, MINIMUM_TEST)
    sonuc = degerlendir(normaller, testler)

    print("=" * 64)
    print("NIHAI KARAR:", sonuc["tahmin"])
    print("GEREKCE:", sonuc["gerekce"])
    print("KUMASA OZEL SAPMA ESIGI:", f"{sonuc['sapma_esigi_px']:.3f} px")
    print(
        "KUMASA OZEL CIZGI KALINLIK ESIGI:",
        f"{sonuc['kalinlik_anomalisi_esigi_px']:.3f} px",
    )
    print(
        "KUMASA OZEL TOPLU KAYMA ZARFI:",
        f"{sonuc['profil_medyan_alt_esigi_px']:.3f}",
        "ile",
        f"{sonuc['profil_medyan_ust_esigi_px']:.3f} px",
    )
    print(
        "BELIRGIN SAPMA KANITI:",
        f"{sonuc['bulunan_kanit']}/{len(testler)}",
        f"(gerekli {sonuc['gerekli_kanit']})",
    )
    for sira, kayit in enumerate(testler, start=1):
        durum = "SAPMA" if kayit["esik_asildi"] else "dogal sinirda"
        print(
            f"Tarama {sira}: merkez={kayit['sapma_araligi_px']:.3f} px, "
            f"kalinlik={kayit['kalinlik_anomalisi_px']:.3f} px, "
            f"toplu_konum={kayit['profil_medyan_y_px']:.3f} px - {durum}"
        )
    print("=" * 64)

    args.cikti.parent.mkdir(parents=True, exist_ok=True)
    args.cikti.write_text(
        json.dumps(sonuc, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("Sonuc dosyasi:", args.cikti)


if __name__ == "__main__":
    main()
