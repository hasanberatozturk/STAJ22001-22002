"""
İş Paketi 7 - Random Forest eğitim çalışması

Amaç:
1. Kalibreli lazer profili özelliklerini CSV'den okumak.
2. Veriyi kumaş bazında train/validation/test olarak ayırmak.
3. Random Forest modelini eğitmek ve değerlendirmek.
4. Eğitilen modeli ve sonuçları kaydetmek.
"""

import csv
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


KLASOR = Path(__file__).resolve().parent
CSV_DOSYASI = KLASOR / "veri" / "wp7_ozellikler.csv"

# Eğitilen model Git dışındaki output/ klasörüne kaydedilir.
MODEL_DOSYASI = KLASOR.parent / "output" / "staj2" / "wp7_random_forest_ogrenci.joblib"


# İlk eğitimde Random Forest'ın en önemli bulduğu beş özellikle başlayacağız.
OZELLIKLER = [
    "sapma_p95_gurultu_orani",
    "sapma_std_px",
    "sapma_medyan_px",
    "sapma_p90_px",
    "aktif_oran_0_5px",
]


def veriyi_oku():
    """CSV'yi okuyup X/y dizilerini train, validation ve test olarak ayırır."""
    veri = {
        "train": {"X": [], "y": []},
        "validation": {"X": [], "y": []},
        "test": {"X": [], "y": []},
    }

    with CSV_DOSYASI.open("r", encoding="utf-8-sig", newline="") as dosya:
        okuyucu = csv.DictReader(dosya)

        for satir in okuyucu:
            split = satir["split"]
            x_satiri = [
                float(satir[ozellik])
                for ozellik in OZELLIKLER
            ]
            y_degeri = int(satir["gercek_sinif"])

            veri[split]["X"].append(x_satiri)
            veri[split]["y"].append(y_degeri)

    # Listeleri scikit-learn'ün kullanacağı NumPy dizilerine dönüştürüyoruz.
    for split in veri:
        veri[split]["X"] = np.asarray(veri[split]["X"], dtype=float)
        veri[split]["y"] = np.asarray(veri[split]["y"], dtype=int)

    return veri


def random_forest_egit(veri):
    """Random Forest modelini yalnızca eğitim grubuyla eğitir."""
    model = RandomForestClassifier(
        n_estimators=400,
        min_samples_leaf=4,
        max_features=0.7,
        class_weight="balanced",
        random_state=42,
        n_jobs=-1,
    )
    model.fit(veri["train"]["X"], veri["train"]["y"])
    return model


def tahmin_yap(model, veri, split):
    """Seçilen veri grubunda gerçek etiketleri ve model tahminlerini döndürür."""
    X = veri[split]["X"]
    y_gercek = veri[split]["y"]
    y_tahmin = model.predict(X)
    return y_gercek, y_tahmin


def metrikleri_hesapla(y_gercek, y_tahmin):
    """İkili sınıflandırma metriklerini ve karmaşıklık matrisini hesaplar."""
    tn, fp, fn, tp = confusion_matrix(
        y_gercek,
        y_tahmin,
        labels=[0, 1],
    ).ravel()

    return {
        "dogruluk": accuracy_score(y_gercek, y_tahmin),
        "kesinlik": precision_score(y_gercek, y_tahmin),
        "duyarlilik": recall_score(y_gercek, y_tahmin),
        "f1": f1_score(y_gercek, y_tahmin),
        "dengeli_dogruluk": balanced_accuracy_score(y_gercek, y_tahmin),
        "tn": int(tn),
        "fp": int(fp),
        "fn": int(fn),
        "tp": int(tp),
    }


def ozellik_onemlerini_goster(model):
    """Random Forest özellik önemlerini büyükten küçüğe yazdırır."""
    eslesmeler = list(zip(OZELLIKLER, model.feature_importances_))
    sirali_ozellikler = sorted(
        eslesmeler,
        key=lambda eleman: eleman[1],
        reverse=True,
    )

    print("\nRandom Forest özellik önemleri")
    for ozellik_adi, onem in sirali_ozellikler:
        print(
            ozellik_adi,
            f"%{onem * 100:.2f}",
        )


def modeli_kaydet(model):
    """Eğitilmiş Random Forest modelini joblib dosyasına kaydeder."""
    MODEL_DOSYASI.parent.mkdir(parents=True, exist_ok=True)
    dump(model, MODEL_DOSYASI)
    print("Model kaydedildi:", MODEL_DOSYASI)


if __name__ == "__main__":
    veri = veriyi_oku()

    for split in ("train", "validation", "test"):
        print(
            split,
            "X boyutu:", veri[split]["X"].shape,
            "y boyutu:", veri[split]["y"].shape,
        )

    model = random_forest_egit(veri)
    print("Eğitilen karar ağacı sayısı:", len(model.estimators_))

    for split in ("validation", "test"):
        y_gercek, y_tahmin = tahmin_yap(model, veri, split)
        metrikler = metrikleri_hesapla(y_gercek, y_tahmin)

        print(f"\n{split} sonuçları")
        for metrik_adi, deger in metrikler.items():
            if metrik_adi in ("tn", "fp", "fn", "tp"):
                print(metrik_adi, deger)
            else:
                print(
                    metrik_adi,
                    f"%{deger * 100:.2f}",
                )

    ozellik_onemlerini_goster(model)
    modeli_kaydet(model)
