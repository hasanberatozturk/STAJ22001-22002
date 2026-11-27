"""İş Paketi 8 - Random Forest çevrim dışı çalışma testi.

Bu program WP7'de kaydedilen modeli yükler, özellik CSV'sindeki satırları
modelin beklediği sırada hazırlar ve NORMAL/KUSUR tahmini üretir.

Örnek:
    python WP8_offline_tahmin.py --split test
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path


PROJE_KOKU = Path(__file__).resolve().parents[1]
PAKET_ADAYLARI = (
    PROJE_KOKU / "work" / "wp8_deps",
    PROJE_KOKU / "work" / "python_deps",
)
for paket_klasoru in PAKET_ADAYLARI:
    if paket_klasoru.is_dir():
        sys.path.insert(0, str(paket_klasoru))
        break

from joblib import load  # noqa: E402
import numpy as np  # noqa: E402


WP7_KLASORU = PROJE_KOKU / "outputs" / "WP7_model_karsilastirma_20260818"
VARSAYILAN_MODEL = WP7_KLASORU / "wp7_random_forest_degerlendirme.joblib"
VARSAYILAN_BILGI = WP7_KLASORU / "wp7_model_bilgileri.json"
VARSAYILAN_CSV = WP7_KLASORU / "wp7_ozellikler.csv"
VARSAYILAN_CIKTI = PROJE_KOKU / "outputs" / "WP8_cevrimdisi_tahmin_20260819"


def argumanlari_oku() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="WP7 Random Forest modelini çevrim dışı doğrular."
    )
    parser.add_argument("--model", type=Path, default=VARSAYILAN_MODEL)
    parser.add_argument("--bilgi", type=Path, default=VARSAYILAN_BILGI)
    parser.add_argument("--csv", type=Path, default=VARSAYILAN_CSV)
    parser.add_argument(
        "--split",
        choices=("train", "validation", "test", "hepsi"),
        default="test",
    )
    parser.add_argument("--cikti", type=Path, default=VARSAYILAN_CIKTI)
    return parser.parse_args()


def json_oku(dosya: Path) -> dict:
    with dosya.open("r", encoding="utf-8") as kaynak:
        return json.load(kaynak)


def csv_oku(dosya: Path, split: str) -> list[dict[str, str]]:
    with dosya.open("r", encoding="utf-8-sig", newline="") as kaynak:
        satirlar = list(csv.DictReader(kaynak))
    if split != "hepsi":
        satirlar = [satir for satir in satirlar if satir["split"] == split]
    if not satirlar:
        raise ValueError(f"Seçilen grupta satır bulunamadı: {split}")
    return satirlar


def girdi_matrisi_olustur(
    satirlar: list[dict[str, str]], ozellikler: list[str]
) -> np.ndarray:
    eksik = [ad for ad in ozellikler if ad not in satirlar[0]]
    if eksik:
        raise ValueError("CSV'de eksik özellikler: " + ", ".join(eksik))
    return np.asarray(
        [[float(satir[ad]) for ad in ozellikler] for satir in satirlar],
        dtype=float,
    )


def metrikleri_hesapla(gercek: np.ndarray, tahmin: np.ndarray) -> dict:
    tn = int(np.sum((gercek == 0) & (tahmin == 0)))
    fp = int(np.sum((gercek == 0) & (tahmin == 1)))
    fn = int(np.sum((gercek == 1) & (tahmin == 0)))
    tp = int(np.sum((gercek == 1) & (tahmin == 1)))

    def guvenli_bol(pay: float, payda: float) -> float:
        return pay / payda if payda else 0.0

    kesinlik = guvenli_bol(tp, tp + fp)
    duyarlilik = guvenli_bol(tp, tp + fn)
    ozgulluk = guvenli_bol(tn, tn + fp)
    return {
        "dogruluk": guvenli_bol(tp + tn, len(gercek)),
        "kesinlik": kesinlik,
        "duyarlilik": duyarlilik,
        "ozgulluk": ozgulluk,
        "f1": guvenli_bol(2 * kesinlik * duyarlilik, kesinlik + duyarlilik),
        "dengeli_dogruluk": (duyarlilik + ozgulluk) / 2,
        "tn": tn,
        "fp": fp,
        "fn": fn,
        "tp": tp,
        "ornek_sayisi": int(len(gercek)),
    }


def sonuclari_yaz(
    dosya: Path,
    satirlar: list[dict[str, str]],
    tahmin: np.ndarray,
    kusur_olasiligi: np.ndarray,
) -> None:
    alanlar = [
        "cift_id",
        "numune",
        "kosul",
        "tekrar",
        "split",
        "gercek_sinif",
        "tahmin_sinif",
        "tahmin_etiketi",
        "kusur_olasiligi",
        "dogru_mu",
    ]
    with dosya.open("w", encoding="utf-8-sig", newline="") as hedef:
        yazici = csv.DictWriter(hedef, fieldnames=alanlar)
        yazici.writeheader()
        for satir, sinif, olasilik in zip(satirlar, tahmin, kusur_olasiligi):
            gercek = int(satir["gercek_sinif"])
            yazici.writerow(
                {
                    "cift_id": satir["cift_id"],
                    "numune": satir["numune"],
                    "kosul": satir["kosul"],
                    "tekrar": satir["tekrar"],
                    "split": satir["split"],
                    "gercek_sinif": gercek,
                    "tahmin_sinif": int(sinif),
                    "tahmin_etiketi": "KUSUR" if int(sinif) else "NORMAL",
                    "kusur_olasiligi": f"{float(olasilik):.6f}",
                    "dogru_mu": int(gercek == int(sinif)),
                }
            )


def main() -> None:
    args = argumanlari_oku()
    for gerekli in (args.model, args.bilgi, args.csv):
        if not gerekli.is_file():
            raise FileNotFoundError(f"Dosya bulunamadı: {gerekli}")

    bilgi = json_oku(args.bilgi)
    ozellikler = bilgi["feature_columns"]
    model = load(args.model)

    model_ozellik_sayisi = int(model.n_features_in_)
    if model_ozellik_sayisi != len(ozellikler):
        raise ValueError(
            "Model/özellik uyuşmazlığı: "
            f"model {model_ozellik_sayisi}, bilgi dosyası {len(ozellikler)}"
        )

    satirlar = csv_oku(args.csv, args.split)
    X = girdi_matrisi_olustur(satirlar, ozellikler)
    gercek = np.asarray([int(satir["gercek_sinif"]) for satir in satirlar])
    tahmin = model.predict(X).astype(int)
    kusur_olasiligi = model.predict_proba(X)[:, 1]
    metrikler = metrikleri_hesapla(gercek, tahmin)

    args.cikti.mkdir(parents=True, exist_ok=True)
    tahmin_dosyasi = args.cikti / f"wp8_{args.split}_tahminleri.csv"
    metrik_dosyasi = args.cikti / f"wp8_{args.split}_metrikleri.json"
    sonuclari_yaz(tahmin_dosyasi, satirlar, tahmin, kusur_olasiligi)
    metrik_dosyasi.write_text(
        json.dumps(
            {
                "model": str(args.model),
                "split": args.split,
                "ozellik_sayisi": len(ozellikler),
                "metrikler": metrikler,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print("Model başarıyla yüklendi:", args.model.name)
    print("Kullanılan özellik sayısı:", len(ozellikler))
    print("Değerlendirilen örnek sayısı:", len(satirlar))
    for ad, deger in metrikler.items():
        if ad in {"tn", "fp", "fn", "tp", "ornek_sayisi"}:
            print(f"{ad}: {deger}")
        else:
            print(f"{ad}: %{deger * 100:.2f}")
    print("Tahminler:", tahmin_dosyasi)
    print("Metrikler:", metrik_dosyasi)


if __name__ == "__main__":
    main()
