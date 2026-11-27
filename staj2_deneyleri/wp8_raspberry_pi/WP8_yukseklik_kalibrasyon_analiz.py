"""WP8 bilinen yukseklik cekimlerinden profil ozelliklerini cikartir."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import numpy as np

from WP8_canli_tahmin import (
    ANALIZ_SAG,
    ANALIZ_SOL,
    X0,
    goruntu_ciftlerini_isle,
    kalibrasyonu_oku,
    kalibrasyon_sorunlarini_bul,
    ozellikleri_cikar,
)


TEPE_MERKEZ_X_MIN = 1050
TEPE_MERKEZ_X_MAX = 1250


def dosyalari_bul(klasor: Path, numune_id: str, durum: str) -> list[Path]:
    return [klasor / f"{numune_id}_{durum}_{i:02d}.jpg" for i in range(1, 4)]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--deney", type=Path, required=True)
    parser.add_argument("--son-numuneyi-kontrol-et", action="store_true")
    args = parser.parse_args()

    deney = args.deney.resolve()
    manifest = deney / "yukseklik_manifest.csv"
    kalibrasyon = deney / "kalibrasyon"
    olcumler = deney / "olcumler"

    referans_iz, referans_guc, gurultu, renk_mesafesi = kalibrasyonu_oku(
        kalibrasyon
    )
    sorunlar, kalibrasyon_lazer_gucu = kalibrasyon_sorunlarini_bul(
        referans_guc,
        gurultu,
        renk_mesafesi,
    )
    if sorunlar:
        raise SystemExit("Kalibrasyon gecersiz: " + "; ".join(sorunlar))

    satirlar = []
    with manifest.open("r", encoding="utf-8-sig", newline="") as dosya:
        for kayit in csv.DictReader(dosya):
            numune_id = kayit["numune_id"]
            numune_klasoru = olcumler / numune_id
            aciklar = dosyalari_bul(numune_klasoru, numune_id, "A")
            kapalilar = dosyalari_bul(numune_klasoru, numune_id, "K")
            eksikler = [p.name for p in aciklar + kapalilar if not p.is_file()]
            if eksikler:
                raise FileNotFoundError(
                    f"{numune_id} eksik goruntuler: " + ", ".join(eksikler)
                )

            iz, guc = goruntu_ciftlerini_isle(aciklar, kapalilar)
            ozellikler = ozellikleri_cikar(
                iz,
                guc,
                referans_iz,
                referans_guc,
                gurultu,
            )
            x = np.arange(X0, X0 + len(iz))
            analiz = (x >= ANALIZ_SOL) & (x <= ANALIZ_SAG)
            fark = (iz - referans_iz)[analiz]
            mutlak = np.abs(fark)
            analiz_x = x[analiz]
            pencere = np.ones(31, dtype=float) / 31.0
            yumusak_mutlak = np.convolve(mutlak, pencere, mode="same")
            tepe_indeksi = int(np.argmax(yumusak_mutlak))
            tepe_merkez_x = int(analiz_x[tepe_indeksi])
            yerel_sol = max(0, tepe_indeksi - 20)
            yerel_sag = min(len(mutlak), tepe_indeksi + 21)
            yerel_mutlak = mutlak[yerel_sol:yerel_sag]
            tepe_konum_gecerli = (
                TEPE_MERKEZ_X_MIN <= tepe_merkez_x <= TEPE_MERKEZ_X_MAX
            )
            tepe_esigi = max(0.5, 3.0 * gurultu)
            belirgin = mutlak >= tepe_esigi
            belirgin_medyan = (
                float(np.median(mutlak[belirgin])) if np.any(belirgin) else 0.0
            )
            olcum_sinyal_gecerli = (
                ozellikler["lazer_gucu_medyan"] >= 10.0
                and ozellikler["lazer_kayip_orani"] <= 0.50
            )
            numune_gecerli = tepe_konum_gecerli and olcum_sinyal_gecerli
            satirlar.append(
                {
                    **kayit,
                    "kalibrasyon_gurultu_p95_px": gurultu,
                    "kalibrasyon_lazer_gucu_medyan": kalibrasyon_lazer_gucu,
                    "belirgin_sapma_esigi_px": tepe_esigi,
                    "belirgin_sapma_medyan_px": belirgin_medyan,
                    "tepe_merkez_x": tepe_merkez_x,
                    "tepe_konum_gecerli": int(tepe_konum_gecerli),
                    "olcum_sinyal_gecerli": int(olcum_sinyal_gecerli),
                    "numune_gecerli": int(numune_gecerli),
                    "yerel_sapma_medyan_px": float(np.median(yerel_mutlak)),
                    "yerel_sapma_p95_px": float(
                        np.percentile(yerel_mutlak, 95)
                    ),
                    **ozellikler,
                }
            )

    cikti_csv = deney / "yukseklik_olcumleri.csv"
    if not satirlar:
        raise SystemExit("Analiz edilecek yukseklik olcumu bulunamadi.")
    with cikti_csv.open("w", encoding="utf-8-sig", newline="") as dosya:
        yazici = csv.DictWriter(dosya, fieldnames=list(satirlar[0]))
        yazici.writeheader()
        yazici.writerows(satirlar)

    ozet = {
        "deney": str(deney),
        "olcum_sayisi": len(satirlar),
        "kalibrasyon_gurultu_p95_px": gurultu,
        "kalibrasyon_lazer_gucu_medyan": kalibrasyon_lazer_gucu,
        "referans_bant_renk_mesafesi": renk_mesafesi,
        "not": "Piksel-mm modeli veri bilgisayarda incelendikten sonra secilecektir.",
    }
    cikti_json = deney / "yukseklik_kalibrasyon_ozeti.json"
    cikti_json.write_text(
        json.dumps(ozet, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print("Analiz edilen yukseklik sayisi:", len(satirlar))
    print(
        "Merkez konumu gecerli olcum sayisi:",
        sum(int(s["tepe_konum_gecerli"]) for s in satirlar),
    )
    print(
        "Konum ve sinyal birlikte gecerli olcum sayisi:",
        sum(int(s["numune_gecerli"]) for s in satirlar),
    )
    print("Olcum CSV:", cikti_csv)
    print("Kalibrasyon ozeti:", cikti_json)
    if args.son_numuneyi_kontrol_et:
        son = satirlar[-1]
        print("Son numune:", son["numune_id"])
        print("Tespit edilen tepe x konumu:", son["tepe_merkez_x"])
        if not int(son["olcum_sinyal_gecerli"]):
            print(
                "SINYAL GECERSIZ: Lazer cizgisi guvenilir bicimde "
                "ayristirilamadi. Lazer durumlarini kontrol edin."
            )
            raise SystemExit(2)
        if not int(son["tepe_konum_gecerli"]):
            print(
                "KONUM GECERSIZ: Yukselti goruntunun orta bolumunde degil. "
                f"Beklenen x araligi {TEPE_MERKEZ_X_MIN}-{TEPE_MERKEZ_X_MAX}."
            )
            raise SystemExit(2)
        print("Konum gecerli. Sonraki yukseklige gecebilirsiniz.")


if __name__ == "__main__":
    main()
