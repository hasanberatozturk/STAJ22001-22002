"""Staj-2 model karşılaştırma sonuçlarının defterdeki değerlerle aynı kaldığını kontrol eder.

Çalıştırma:
    python -m unittest discover -s staj2_deneyleri -p "test_*.py" -v
"""

import csv
import unittest
from pathlib import Path

try:
    import sklearn  # noqa: F401
    SKLEARN_VAR = True
except ImportError:
    SKLEARN_VAR = False

CSV_DOSYASI = Path(__file__).resolve().parent / "veri" / "wp7_ozellikler.csv"


def karmasiklik(y_gercek, y_tahmin):
    """TN, FP, FN, TP değerlerini sırayla döndürür (pozitif sınıf = kusur)."""
    tn = fp = fn = tp = 0
    for gercek, tahmin in zip(y_gercek, y_tahmin):
        if gercek == 0 and tahmin == 0:
            tn += 1
        elif gercek == 0 and tahmin == 1:
            fp += 1
        elif gercek == 1 and tahmin == 0:
            fn += 1
        else:
            tp += 1
    return tn, fp, fn, tp


class VeriBolmeTesti(unittest.TestCase):
    def test_bolme_kumas_bazinda(self):
        """Her kumaş yalnızca tek bir veri grubunda bulunmalıdır (veri sızıntısı yok)."""
        with CSV_DOSYASI.open(encoding="utf-8-sig", newline="") as dosya:
            satirlar = list(csv.DictReader(dosya))
        gruplar: dict[str, set[str]] = {}
        for satir in satirlar:
            gruplar.setdefault(satir["numune"], set()).add(satir["split"])
        for numune, bolmeler in gruplar.items():
            self.assertEqual(len(bolmeler), 1, numune)

        sayilar = {"train": 0, "validation": 0, "test": 0}
        for satir in satirlar:
            sayilar[satir["split"]] += 1
        self.assertEqual(sayilar, {"train": 90, "validation": 18, "test": 18})

    def test_esik_yontemi_k011(self):
        """sapma_std_px >= 0,431129 kuralı K011'de 16/18 doğru olmalıdır."""
        with CSV_DOSYASI.open(encoding="utf-8-sig", newline="") as dosya:
            test = [s for s in csv.DictReader(dosya) if s["split"] == "test"]
        y_gercek = [int(s["gercek_sinif"]) for s in test]
        y_tahmin = [int(float(s["sapma_std_px"]) >= 0.431129) for s in test]
        self.assertEqual(karmasiklik(y_gercek, y_tahmin), (2, 1, 1, 14))


@unittest.skipUnless(SKLEARN_VAR, "scikit-learn kurulu değil")
class ModelTesti(unittest.TestCase):
    def test_random_forest_k011(self):
        import WP7_random_forest_ogrenci as rf

        veri = rf.veriyi_oku()
        model = rf.random_forest_egit(veri)
        y_gercek, y_tahmin = rf.tahmin_yap(model, veri, "test")
        self.assertEqual(karmasiklik(y_gercek, y_tahmin), (3, 0, 0, 15))

    def test_svm_k011(self):
        import WP7_svm_ogrenci as svm

        veri = svm.veriyi_oku()
        secim = svm.en_iyi_svm_ayarlarini_bul(veri)
        self.assertEqual((secim["C"], secim["gamma"]), (0.1, "scale"))
        y_gercek, y_tahmin = svm.tahmin_yap(secim["model"], veri, "test")
        self.assertEqual(karmasiklik(y_gercek, y_tahmin), (2, 1, 1, 14))


if __name__ == "__main__":
    unittest.main()
