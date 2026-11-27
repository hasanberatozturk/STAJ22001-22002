"""WP8 V4 optik doğrulama yardımcısı.

Makine öğrenmesi modelini çalıştırmadan önce kamera odağını, lazer pozlamasını
ve bilinen 5 mm basamağın profil üzerinde ölçülebilir olup olmadığını denetler.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import numpy as np
from PIL import Image

from WP8_canli_tahmin import (
    ANALIZ_SAG,
    ANALIZ_SOL,
    X0,
    goruntu_ciftini_isle,
)


def gri_oku(yol: Path) -> np.ndarray:
    with Image.open(yol) as goruntu:
        return np.asarray(goruntu.convert("L"), dtype=np.float32)


def netlik_puani(yol: Path) -> float:
    """Görüntüdeki yüksek frekanslı ayrıntıyı ölçer; büyük değer daha nettir."""
    gri = gri_oku(yol)
    # Kenar bölgeleri ve düzenek görüntüsü kararı bozmasın diye orta alan.
    h, w = gri.shape
    roi = gri[h // 4 : 3 * h // 4, w // 4 : 3 * w // 4]
    lap = (
        -4.0 * roi[1:-1, 1:-1]
        + roi[:-2, 1:-1]
        + roi[2:, 1:-1]
        + roi[1:-1, :-2]
        + roi[1:-1, 2:]
    )
    return float(np.var(lap))


def odak_sec(klasor: Path, cikti: Path) -> None:
    adaylar = []
    for yol in sorted(klasor.glob("odak_*.jpg")):
        eslesme = re.search(r"odak_([0-9.]+)\.jpg$", yol.name)
        if eslesme:
            adaylar.append(
                {
                    "lens_position": float(eslesme.group(1)),
                    "netlik_puani": netlik_puani(yol),
                    "dosya": str(yol),
                }
            )
    if len(adaylar) < 3:
        raise SystemExit("HATA: En az üç odak deneme görüntüsü bulunamadı.")
    en_iyi = max(adaylar, key=lambda x: x["netlik_puani"])
    sonuc = {"lens_position": en_iyi["lens_position"], "adaylar": adaylar}
    cikti.write_text(json.dumps(sonuc, indent=2), encoding="utf-8")
    print(f"SECILEN_ODAK={en_iyi['lens_position']:.2f}")
    for aday in adaylar:
        print(
            f"  odak={aday['lens_position']:.2f} "
            f"netlik={aday['netlik_puani']:.2f}"
        )


def lazer_sinyali(acik: Path, kapali: Path) -> tuple[float, float]:
    _, guc = goruntu_ciftini_isle(acik, kapali)
    x = np.arange(X0, X0 + len(guc))
    analiz = (x >= ANALIZ_SOL) & (x <= ANALIZ_SAG)
    sinyal = float(np.median(guc[analiz]))
    with Image.open(acik) as goruntu:
        rgb = np.asarray(goruntu.convert("RGB"), dtype=np.uint8)
    roi = rgb[500:800, ANALIZ_SOL:ANALIZ_SAG]
    # Kırmızı kanalın tavana dayanması centroid hesabını bozabilir.
    tasma = float(np.mean(roi[..., 0] >= 252))
    return sinyal, tasma


def pozlama_sec(klasor: Path, cikti: Path) -> None:
    adaylar = []
    for kapali in sorted(klasor.glob("pozlama_*_K.jpg")):
        eslesme = re.search(r"pozlama_(\d+)_K\.jpg$", kapali.name)
        if not eslesme:
            continue
        shutter = int(eslesme.group(1))
        acik = klasor / f"pozlama_{shutter}_A.jpg"
        if not acik.is_file():
            continue
        sinyal, tasma = lazer_sinyali(acik, kapali)
        adaylar.append(
            {
                "shutter_us": shutter,
                "lazer_gucu_medyan": sinyal,
                "kirmizi_tasma_orani": tasma,
            }
        )
    if len(adaylar) < 3:
        raise SystemExit("HATA: Üç pozlama denemesi eksiksiz bulunamadı.")
    uygun = [a for a in adaylar if a["kirmizi_tasma_orani"] <= 0.02]
    if not uygun:
        raise SystemExit("HATA: Bütün pozlamalarda kırmızı kanal taştı.")
    en_iyi = max(uygun, key=lambda x: x["lazer_gucu_medyan"])
    if en_iyi["lazer_gucu_medyan"] < 25.0:
        raise SystemExit(
            "HATA: En iyi pozlamada bile lazer sinyali çok zayıf. "
            "Lazer açısını/gücünü ve ortam ışığını kontrol edin."
        )
    sonuc = {"shutter_us": en_iyi["shutter_us"], "adaylar": adaylar}
    cikti.write_text(json.dumps(sonuc, indent=2), encoding="utf-8")
    print(f"SECILEN_POZLAMA={en_iyi['shutter_us']}")
    for aday in adaylar:
        print(
            f"  shutter={aday['shutter_us']} us "
            f"lazer={aday['lazer_gucu_medyan']:.2f} "
            f"tasma=%{100 * aday['kirmizi_tasma_orani']:.3f}"
        )


def profil_medyan(klasor: Path, onek: str) -> np.ndarray:
    izler = []
    for tekrar in range(1, 4):
        kapali = klasor / f"{onek}_K_{tekrar:02d}.jpg"
        acik = klasor / f"{onek}_A_{tekrar:02d}.jpg"
        if not kapali.is_file() or not acik.is_file():
            raise SystemExit(f"HATA: Eksik görüntü çifti: {kapali.name}/{acik.name}")
        iz, _ = goruntu_ciftini_isle(acik, kapali)
        izler.append(iz)
    return np.median(np.stack(izler), axis=0)


def optik_dogrula(klasor: Path, cikti: Path) -> None:
    duz_tekrarlar = []
    for tekrar in range(1, 4):
        iz, _ = goruntu_ciftini_isle(
            klasor / f"DUZ_A_{tekrar:02d}.jpg",
            klasor / f"DUZ_K_{tekrar:02d}.jpg",
        )
        duz_tekrarlar.append(iz)
    duz = np.median(np.stack(duz_tekrarlar), axis=0)
    basamak = profil_medyan(klasor, "BASAMAK5MM")

    x = np.arange(X0, X0 + len(duz))
    analiz = (x >= ANALIZ_SOL) & (x <= ANALIZ_SAG)
    gurultu = np.concatenate(
        [np.abs(iz[analiz] - duz[analiz]) for iz in duz_tekrarlar]
    )
    gurultu_p95 = float(np.percentile(gurultu, 95))
    fark = np.abs((basamak - duz)[analiz])
    fark_p95 = float(np.percentile(fark, 95))
    fark_maks = float(np.max(fark))
    aktif_oran = float(np.mean(fark >= max(0.75, 5.0 * gurultu_p95)))

    p95_esigi = max(0.75, 5.0 * gurultu_p95)
    maks_esigi = max(1.50, 8.0 * gurultu_p95)
    gecti = (
        gurultu_p95 <= 0.60
        and fark_p95 >= p95_esigi
        and fark_maks >= maks_esigi
        and aktif_oran >= 0.02
    )
    sonuc = {
        "optik_dogrulama": "GECTI" if gecti else "KALDI",
        "kalibrasyon_gurultu_p95_px": gurultu_p95,
        "basamak_fark_p95_px": fark_p95,
        "basamak_fark_maks_px": fark_maks,
        "basamak_aktif_oran": aktif_oran,
        "gereken_p95_px": p95_esigi,
        "gereken_maks_px": maks_esigi,
    }
    cikti.write_text(json.dumps(sonuc, indent=2), encoding="utf-8")
    print("=" * 60)
    print("OPTIK DOGRULAMA:", sonuc["optik_dogrulama"])
    print(f"Düz yüzey gürültüsü p95 : {gurultu_p95:.3f} px")
    print(f"5 mm basamak farkı p95  : {fark_p95:.3f} px")
    print(f"5 mm basamak maksimumu  : {fark_maks:.3f} px")
    print(f"Anlamlı aktif alan       : %{100 * aktif_oran:.2f}")
    if not gecti:
        print("MODELİ ÇALIŞTIRMAYIN: Kamera-lazer geometrisi 5 mm basamağı ayıramadı.")
    else:
        print("Ölçüm zinciri doğrulandı. Kumaş testlerine geçilebilir.")
    print("=" * 60)
    raise SystemExit(0 if gecti else 2)


def main() -> None:
    parser = argparse.ArgumentParser()
    alt = parser.add_subparsers(dest="komut", required=True)
    for ad in ("odak-sec", "pozlama-sec", "dogrula"):
        p = alt.add_parser(ad)
        p.add_argument("--klasor", type=Path, required=True)
        p.add_argument("--cikti", type=Path, required=True)
    args = parser.parse_args()
    if args.komut == "odak-sec":
        odak_sec(args.klasor, args.cikti)
    elif args.komut == "pozlama-sec":
        pozlama_sec(args.klasor, args.cikti)
    else:
        optik_dogrula(args.klasor, args.cikti)


if __name__ == "__main__":
    main()
