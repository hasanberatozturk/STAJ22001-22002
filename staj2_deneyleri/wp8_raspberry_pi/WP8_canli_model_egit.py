"""WP8 canlı üçlü çekimlerinden oturum bazlı doğrulamayla model eğitir."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path

import numpy as np
from joblib import dump
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)
from sklearn.model_selection import LeaveOneGroupOut


GECERLI_OTURUMLAR = (
    "20260820_131356",
    "20260820_134430",
    "20260820_141645",
    "20260820_194007",
    "20260821_183702",
    "20260821_191520",
    "20260821_194247",
    "20260821_210731",
    "20260822_112136",
    "20260822_121845",
)

# İş Paketi 8'in nihai kapsamı:
# 0 = normal, 1-4 = sırt / kabarıklık / kırışıklık kusurları.
# Kat izi kodları (5 ve 6), mevcut tek lazer çizgisiyle kırışıklıktan
# güvenilir biçimde ayrılamadığı için eğitime ve metriklere alınmaz.
GECERLI_KODLAR = {"0", "1", "2", "3", "4"}

KOMPAKT_OZELLIKLER = [
    "sapma_medyan_px",
    "sapma_p95_px",
    "sapma_std_px",
    "aktif_oran_0_5px",
    "aktif_oran_1px",
    "en_uzun_aktif_seri_1px",
    "sapma_p95_gurultu_orani",
    "gurultu_ustu_aktif_oran",
]


def metrikleri_hesapla(y_gercek: np.ndarray, y_tahmin: np.ndarray) -> dict:
    tn, fp, fn, tp = confusion_matrix(y_gercek, y_tahmin, labels=[0, 1]).ravel()
    return {
        "dogruluk": float(accuracy_score(y_gercek, y_tahmin)),
        "kesinlik": float(precision_score(y_gercek, y_tahmin, zero_division=0)),
        "duyarlilik": float(recall_score(y_gercek, y_tahmin, zero_division=0)),
        "ozgulluk": float(tn / max(1, tn + fp)),
        "f1": float(f1_score(y_gercek, y_tahmin, zero_division=0)),
        "dengeli_dogruluk": float(balanced_accuracy_score(y_gercek, y_tahmin)),
        "tn": int(tn),
        "fp": int(fp),
        "fn": int(fn),
        "tp": int(tp),
    }


def kayitlari_oku(kok: Path, ozellikler: list[str]) -> list[dict]:
    kayitlar = []
    for oturum in GECERLI_OTURUMLAR:
        klasor = kok / oturum / "olcumler"
        if not klasor.is_dir():
            raise FileNotFoundError(f"Oturum bulunamadı: {klasor}")
        for dosya in sorted(klasor.glob("olcum_*_sonuc.json")):
            sonuc = json.loads(dosya.read_text(encoding="utf-8"))
            gercek_kod = str(sonuc["gercek_kod"])
            if gercek_kod not in GECERLI_KODLAR:
                print(
                    "KAPSAM DIŞI:",
                    oturum,
                    dosya.name,
                    sonuc.get("gercek_etiket", "bilinmiyor"),
                )
                continue
            olcum_ozellikleri = sonuc["ozellikler"]
            sorunlar = []
            if not sonuc.get("olcum_gecerli", False):
                sorunlar.append("ölçüm geçersiz")
            if float(sonuc["kalibrasyon_gurultu_p95_px"]) > 2.0:
                sorunlar.append("kalibrasyon gürültüsü yüksek")
            if float(sonuc.get("referans_bant_renk_mesafesi", 999.0)) > 8.0:
                sorunlar.append("referans bantları uyumsuz")
            if float(olcum_ozellikleri["lazer_kayip_orani"]) > 0.50:
                sorunlar.append("lazer kaybı yüksek")
            if sorunlar:
                print("ATLANDI:", oturum, dosya.name, "; ".join(sorunlar))
                continue
            eksik = [ad for ad in ozellikler if ad not in olcum_ozellikleri]
            if eksik:
                raise ValueError(f"{dosya}: eksik özellik: {', '.join(eksik)}")
            kayitlar.append(
                {
                    "oturum": oturum,
                    "olcum": dosya.stem.replace("_sonuc", ""),
                    "gercek_kod": gercek_kod,
                    "gercek_etiket": sonuc["gercek_etiket"],
                    # 0 doğal normal yüzeydir; 1-4 hedef geometrik kusurlardır.
                    "y": 0 if gercek_kod == "0" else 1,
                    "ozellikler": {
                        ad: float(olcum_ozellikleri[ad]) for ad in ozellikler
                    },
                }
            )
    return kayitlar


def dizilere_donustur(kayitlar: list[dict], ozellikler: list[str]):
    X = np.asarray(
        [[kayit["ozellikler"][ad] for ad in ozellikler] for kayit in kayitlar],
        dtype=float,
    )
    y = np.asarray([kayit["y"] for kayit in kayitlar], dtype=int)
    gruplar = np.asarray([kayit["oturum"] for kayit in kayitlar])
    return X, y, gruplar


def model_olustur(ayar: dict) -> RandomForestClassifier:
    return RandomForestClassifier(
        n_estimators=400,
        max_depth=ayar["max_depth"],
        min_samples_leaf=ayar["min_samples_leaf"],
        max_features=ayar["max_features"],
        class_weight="balanced",
        random_state=42,
        n_jobs=-1,
    )


def ayarlari_degerlendir(
    kayitlar: list[dict],
    ozellikler: list[str],
    ayar: dict,
) -> tuple[dict, list[dict]]:
    X, y, gruplar = dizilere_donustur(kayitlar, ozellikler)
    logo = LeaveOneGroupOut()
    tum_gercek = []
    tum_tahmin = []
    tahmin_kayitlari = []
    for egitim_indeksleri, test_indeksleri in logo.split(X, y, groups=gruplar):
        model = model_olustur(ayar)
        model.fit(X[egitim_indeksleri], y[egitim_indeksleri])
        tahmin = model.predict(X[test_indeksleri])
        olasilik = model.predict_proba(X[test_indeksleri])[:, 1]
        tum_gercek.extend(y[test_indeksleri].tolist())
        tum_tahmin.extend(tahmin.tolist())
        for indeks, tahmin_degeri, skor in zip(test_indeksleri, tahmin, olasilik):
            tahmin_kayitlari.append(
                {
                    "oturum": kayitlar[indeks]["oturum"],
                    "olcum": kayitlar[indeks]["olcum"],
                    "gercek_etiket": kayitlar[indeks]["gercek_etiket"],
                    "gercek_sinif": int(y[indeks]),
                    "tahmin_sinif": int(tahmin_degeri),
                    "kusur_olasiligi": float(skor),
                }
            )
    return (
        metrikleri_hesapla(np.asarray(tum_gercek), np.asarray(tum_tahmin)),
        tahmin_kayitlari,
    )


def csv_yaz(dosya: Path, satirlar: list[dict], alanlar: list[str]) -> None:
    with dosya.open("w", encoding="utf-8-sig", newline="") as hedef:
        yazici = csv.DictWriter(hedef, fieldnames=alanlar)
        yazici.writeheader()
        yazici.writerows(satirlar)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--veri-koku",
        type=Path,
        default=Path.home() / "WP8_CANLI",
    )
    parser.add_argument(
        "--cikti-klasoru",
        type=Path,
        default=Path(__file__).resolve().parent,
    )
    args = parser.parse_args()
    args.cikti_klasoru.mkdir(parents=True, exist_ok=True)

    bilgi_dosyasi = Path(__file__).resolve().parent / "wp7_model_bilgileri.json"
    eski_bilgi = json.loads(bilgi_dosyasi.read_text(encoding="utf-8"))
    tam_ozellikler = eski_bilgi["feature_columns"]
    kayitlar = kayitlari_oku(args.veri_koku, tam_ozellikler)

    sinif_sayilari = Counter(kayit["y"] for kayit in kayitlar)
    print("Geçerli örnek:", len(kayitlar))
    print("Normal:", sinif_sayilari[0], "Kusur:", sinif_sayilari[1])
    if sinif_sayilari[0] < 2 or sinif_sayilari[1] < 2:
        raise ValueError(
            "Eğitim için her iki sınıfta da en az iki geçerli örnek gerekir."
        )

    aday_sonuclari = []
    en_iyi = None
    for ozellik_seti_adi, ozellikler in (
        ("kompakt_8", KOMPAKT_OZELLIKLER),
        ("tam_26", tam_ozellikler),
    ):
        for max_depth in (2, 3, None):
            for min_samples_leaf in (1, 2, 3):
                for max_features in ("sqrt", 0.7):
                    ayar = {
                        "max_depth": max_depth,
                        "min_samples_leaf": min_samples_leaf,
                        "max_features": max_features,
                    }
                    metrikler, tahminler = ayarlari_degerlendir(
                        kayitlar, ozellikler, ayar
                    )
                    satir = {
                        "ozellik_seti": ozellik_seti_adi,
                        "ozellik_sayisi": len(ozellikler),
                        "max_depth": "None" if max_depth is None else max_depth,
                        "min_samples_leaf": min_samples_leaf,
                        "max_features": max_features,
                        **metrikler,
                    }
                    aday_sonuclari.append(satir)
                    secim_skoru = (
                        metrikler["dengeli_dogruluk"],
                        metrikler["f1"],
                        metrikler["dogruluk"],
                        -len(ozellikler),
                    )
                    if en_iyi is None or secim_skoru > en_iyi["secim_skoru"]:
                        en_iyi = {
                            "secim_skoru": secim_skoru,
                            "ozellik_seti": ozellik_seti_adi,
                            "ozellikler": ozellikler,
                            "ayar": ayar,
                            "metrikler": metrikler,
                            "tahminler": tahminler,
                        }

    assert en_iyi is not None
    X, y, _ = dizilere_donustur(kayitlar, en_iyi["ozellikler"])
    nihai_model = model_olustur(en_iyi["ayar"])
    nihai_model.fit(X, y)

    model_dosyasi = args.cikti_klasoru / "wp8_random_forest_canli.joblib"
    dump(nihai_model, model_dosyasi)

    veri_satirlari = []
    for kayit in kayitlar:
        veri_satirlari.append(
            {
                "oturum": kayit["oturum"],
                "olcum": kayit["olcum"],
                "gercek_kod": kayit["gercek_kod"],
                "gercek_etiket": kayit["gercek_etiket"],
                "gercek_sinif": kayit["y"],
                **kayit["ozellikler"],
            }
        )
    csv_yaz(
        args.cikti_klasoru / "wp8_canli_egitim_verisi.csv",
        veri_satirlari,
        list(veri_satirlari[0]),
    )
    csv_yaz(
        args.cikti_klasoru / "wp8_cv_sonuclari.csv",
        sorted(
            aday_sonuclari,
            key=lambda satir: (
                satir["dengeli_dogruluk"], satir["f1"], satir["dogruluk"]
            ),
            reverse=True,
        ),
        list(aday_sonuclari[0]),
    )
    csv_yaz(
        args.cikti_klasoru / "wp8_cv_tahminleri.csv",
        en_iyi["tahminler"],
        list(en_iyi["tahminler"][0]),
    )
    onemler = sorted(
        zip(en_iyi["ozellikler"], nihai_model.feature_importances_),
        key=lambda oge: oge[1],
        reverse=True,
    )
    csv_yaz(
        args.cikti_klasoru / "wp8_ozellik_onemi.csv",
        [
            {"sira": sira, "ozellik": ad, "onem": float(onem)}
            for sira, (ad, onem) in enumerate(onemler, start=1)
        ],
        ["sira", "ozellik", "onem"],
    )
    model_bilgisi = {
        "hedef": "normal (0) / geometrik kusur (1)",
        "veri_surumu": "WP8 canlı üçlü çekim v4 - kat izi kapsam dışı",
        "oturumlar": list(GECERLI_OTURUMLAR),
        "ornek_sayisi": len(kayitlar),
        "normal_sayisi": sinif_sayilari[0],
        "kusur_sayisi": sinif_sayilari[1],
        "feature_columns": en_iyi["ozellikler"],
        "ozellik_seti": en_iyi["ozellik_seti"],
        # v2 modeli ince kusur örneklerini de içerdiği için eski modeldeki
        # geçici normal geometri kapısına ihtiyaç duymaz.
        "normal_geometri_kapisi": False,
        "siki_normal_aktif_alan_kapisi": True,
        "siki_normal_aktif_oran_esigi": 0.25,
        "siki_normal_sapma_std_esigi": 0.36,
        "siki_normal_sapma_p95_esigi": 0.80,
        "siki_normal_sapma_aralik_esigi": 1.90,
        "random_forest": {
            "n_estimators": 400,
            **en_iyi["ayar"],
            "class_weight": "balanced",
            "random_state": 42,
        },
        "dogrulama": {
            "yontem": "LeaveOneGroupOut - oturum bazlı",
            **en_iyi["metrikler"],
        },
        "kapsam_kodlari": sorted(GECERLI_KODLAR),
        "kapsam_disi": ["5: derin_kat_izi", "6: hafif_kat_izi"],
        "not": (
            "Model normal yüzey ile sırt, kabarıklık ve kırışıklık kusurlarını "
            "ayırt eder. Kat izi eğitim ve değerlendirme kapsamı dışındadır."
        ),
    }
    (args.cikti_klasoru / "wp8_model_bilgileri_canli.json").write_text(
        json.dumps(model_bilgisi, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print("\nSeçilen özellik seti:", en_iyi["ozellik_seti"])
    print("Seçilen ayarlar:", en_iyi["ayar"])
    print("Oturum bazlı CV metrikleri:")
    for ad, deger in en_iyi["metrikler"].items():
        if ad in ("tn", "fp", "fn", "tp"):
            print(f"  {ad}: {deger}")
        else:
            print(f"  {ad}: %{deger * 100:.2f}")
    print("Model kaydedildi:", model_dosyasi)


if __name__ == "__main__":
    main()
