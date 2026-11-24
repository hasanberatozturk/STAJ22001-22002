"""
İş Paketi 7 - SVM eğitim çalışması

Amaç:
1. Random Forest ile aynı beş lazer profili özelliğini kullanmak.
2. Özellikleri StandardScaler ile standartlaştırmak.
3. RBF çekirdekli SVM modelini eğitmek.
4. C ve gamma ayarlarını K003 doğrulama numunesinde seçmek.
5. Seçilen modeli K011 test numunesinde değerlendirmek ve kaydetmek.
"""

import csv
from pathlib import Path

import numpy as np
from joblib import dump
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC


KLASOR = Path(__file__).resolve().parent
CSV_DOSYASI = KLASOR / "veri" / "wp7_ozellikler.csv"

# Eğitilen model Git dışındaki output/ klasörüne kaydedilir.
MODEL_DOSYASI = KLASOR.parent / "output" / "staj2" / "wp7_svm_ogrenci.joblib"

OZELLIKLER = [
    "sapma_p95_gurultu_orani",
    "sapma_std_px",
    "sapma_medyan_px",
    "sapma_p90_px",
    "aktif_oran_0_5px",
]

C_ADAYLARI = [0.1, 1.0, 10.0, 100.0]
GAMMA_ADAYLARI = ["scale", 0.01, 0.1, 1.0]


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
            x_satiri = [float(satir[ozellik]) for ozellik in OZELLIKLER]
            y_degeri = int(satir["gercek_sinif"])
            veri[split]["X"].append(x_satiri)
            veri[split]["y"].append(y_degeri)

    for split in veri:
        veri[split]["X"] = np.asarray(veri[split]["X"], dtype=float)
        veri[split]["y"] = np.asarray(veri[split]["y"], dtype=int)

    return veri


def svm_modeli_olustur(c_degeri, gamma_degeri):
    """StandardScaler ve RBF-SVM adımlarından oluşan modeli kurar."""
    model = Pipeline(
        steps=[
            ("olcekleme", StandardScaler()),
            (
                "siniflandirici",
                SVC(
                    kernel="rbf",
                    C=c_degeri,
                    gamma=gamma_degeri,
                    class_weight="balanced",
                    probability=True,
                    random_state=42,
                ),
            ),
        ]
    )
    return model


def svm_egit(
    veri,
    c_degeri=1.0,
    gamma_degeri="scale",
):
    """SVM pipeline'ını yalnızca eğitim grubuyla eğitir."""
    model = svm_modeli_olustur(
        c_degeri=c_degeri,
        gamma_degeri=gamma_degeri,
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
        "kesinlik": precision_score(y_gercek, y_tahmin, zero_division=0),
        "duyarlilik": recall_score(y_gercek, y_tahmin, zero_division=0),
        "f1": f1_score(y_gercek, y_tahmin, zero_division=0),
        "dengeli_dogruluk": balanced_accuracy_score(y_gercek, y_tahmin),
        "tn": int(tn),
        "fp": int(fp),
        "fn": int(fn),
        "tp": int(tp),
    }


def en_iyi_svm_ayarlarini_bul(veri):
    """C ve gamma adaylarını K003 doğrulama grubunda karşılaştırır."""
    en_iyi_sonuc = None

    for c_degeri in C_ADAYLARI:
        for gamma_degeri in GAMMA_ADAYLARI:
            model = svm_egit(
                veri,
                c_degeri=c_degeri,
                gamma_degeri=gamma_degeri,
            )
            y_gercek, y_tahmin = tahmin_yap(model, veri, "validation")
            metrikler = metrikleri_hesapla(y_gercek, y_tahmin)
            secim_skoru = (
                metrikler["dengeli_dogruluk"],
                metrikler["f1"],
            )

            if (
                en_iyi_sonuc is None
                or secim_skoru > en_iyi_sonuc["secim_skoru"]
            ):
                en_iyi_sonuc = {
                    "model": model,
                    "C": c_degeri,
                    "gamma": gamma_degeri,
                    "metrikler": metrikler,
                    "secim_skoru": secim_skoru,
                }

    return en_iyi_sonuc


def modeli_kaydet(model):
    """Seçilen SVM pipeline'ını joblib dosyasına kaydeder."""
    MODEL_DOSYASI.parent.mkdir(parents=True, exist_ok=True)
    dump(model, MODEL_DOSYASI)
    print("SVM modeli kaydedildi:", MODEL_DOSYASI)


if __name__ == "__main__":
    veri = veriyi_oku()

    for split in ("train", "validation", "test"):
        print(
            split,
            "X boyutu:", veri[split]["X"].shape,
            "y boyutu:", veri[split]["y"].shape,
        )

    ornek_model = svm_modeli_olustur(c_degeri=1.0, gamma_degeri="scale")
    print("SVM pipeline adımları:", list(ornek_model.named_steps.keys()))

    en_iyi_ayarlar = en_iyi_svm_ayarlarini_bul(veri)
    print("En iyi SVM ayarları:")
    print("  C:", en_iyi_ayarlar["C"])
    print("  Gamma:", en_iyi_ayarlar["gamma"])
    print("  Validation metrikleri:")
    for metrik, deger in en_iyi_ayarlar["metrikler"].items():
        print(f"    {metrik}: {deger}")

    svm_siniflandirici = en_iyi_ayarlar["model"].named_steps["siniflandirici"]
    print("Sınıflara göre destek vektörü sayıları:", svm_siniflandirici.n_support_)

    en_iyi_model = en_iyi_ayarlar["model"]
    for split in ("validation", "test"):
        y_gercek, y_tahmin = tahmin_yap(en_iyi_model, veri, split)
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

    modeli_kaydet(en_iyi_model)
