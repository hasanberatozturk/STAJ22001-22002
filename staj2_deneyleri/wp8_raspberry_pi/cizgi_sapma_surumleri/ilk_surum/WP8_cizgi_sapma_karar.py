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


SURUM = "WP8-CIZGI-SAPMA-FINAL-20260823"
MINIMUM_REFERANS = 3
MINIMUM_TEST = 3
GUVENLIK_CARPANI = 1.12
MINIMUM_GUVENLIK_MARJI_PX = 0.20
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


def profil_oku(klasor: Path, onek: str) -> tuple[np.ndarray, float]:
    acik = sorted(klasor.glob(f"{onek}_A_*.jpg"))
    kapali = sorted(klasor.glob(f"{onek}_K_*.jpg"))
    if len(acik) != 3 or len(kapali) != 3:
        raise FileNotFoundError(
            f"{klasor / onek}: 3 lazer acik ve 3 lazer kapali goruntu gerekli."
        )
    profil, guc = ORTAK.goruntu_ciftlerini_isle(acik, kapali)
    return np.asarray(profil, dtype=float), float(np.median(guc))


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


def seriyi_oku(klasor: Path, kok: str, minimum: int) -> list[dict]:
    onekler = onekleri_bul(klasor, kok)
    if len(onekler) < minimum:
        raise ValueError(
            f"{klasor}: en az {minimum} olcum gerekli; bulunan {len(onekler)}."
        )
    kayitlar = []
    for onek in onekler:
        profil, guc = profil_oku(klasor, onek)
        if guc < MINIMUM_LAZER_GUCU:
            raise ValueError(
                f"{onek}: lazer sinyali cok zayif ({guc:.1f}). Olcumu tekrarlayin."
            )
        kayitlar.append(
            {
                "onek": onek,
                "sapma_araligi_px": dogrudan_sapma_araligi(profil),
                "lazer_gucu": guc,
            }
        )
    return kayitlar


def esik_kur(normal_kayitlari: list[dict]) -> float:
    en_kotu_normal = max(k["sapma_araligi_px"] for k in normal_kayitlari)
    return max(
        en_kotu_normal * GUVENLIK_CARPANI,
        en_kotu_normal + MINIMUM_GUVENLIK_MARJI_PX,
    )


def degerlendir(normal_kayitlari: list[dict], test_kayitlari: list[dict]) -> dict:
    esik = esik_kur(normal_kayitlari)
    gerekli_kanit = max(2, math.ceil(len(test_kayitlari) * 0.40))
    for kayit in test_kayitlari:
        kayit["esik_asildi"] = kayit["sapma_araligi_px"] >= esik
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
        "sapma_esigi_px": esik,
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
        "BELIRGIN SAPMA KANITI:",
        f"{sonuc['bulunan_kanit']}/{len(testler)}",
        f"(gerekli {sonuc['gerekli_kanit']})",
    )
    for sira, kayit in enumerate(testler, start=1):
        durum = "SAPMA" if kayit["esik_asildi"] else "dogal sinirda"
        print(f"Tarama {sira}: {kayit['sapma_araligi_px']:.3f} px - {durum}")
    print("=" * 64)

    args.cikti.parent.mkdir(parents=True, exist_ok=True)
    args.cikti.write_text(
        json.dumps(sonuc, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("Sonuc dosyasi:", args.cikti)


if __name__ == "__main__":
    main()
