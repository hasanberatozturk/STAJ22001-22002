"""WP8 - Bir lazer açık/kapalı görüntü çiftinden Random Forest tahmini."""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

PROJE_KOKU = Path(__file__).resolve().parents[2]
YEREL_PAKET_ADAYLARI = []
if os.environ.get("WP8_PYTHON_DEPS"):
    YEREL_PAKET_ADAYLARI.append(Path(os.environ["WP8_PYTHON_DEPS"]))
YEREL_PAKET_ADAYLARI.append(PROJE_KOKU / "work" / "wp8_deps")
for yerel_paketler in YEREL_PAKET_ADAYLARI:
    try:
        if (yerel_paketler / "joblib" / "__init__.py").is_file():
            sys.path.insert(0, str(yerel_paketler))
            break
    except OSError:
        continue

import numpy as np
from PIL import Image


X0, X1 = 650, 1650
Y0, Y1 = 500, 800
ANALIZ_SOL, ANALIZ_SAG = 820, 1480
REFERANS_SOL = (690, 810)
REFERANS_SAG = (1490, 1610)

# WP8 canlı normal tekrarlarından elde edilen geçici güvenli bölge.
# Bu sınırlar nihai model parametresi değildir; bağımsız normal/kusur
# çekimleri arttıkça kaldırılıp yeniden eğitilmiş modelle değiştirilecektir.
# Üç açık/kapalı çiftin medyan profilindeki yerel tepe sınırları.
# Oranlar, günler arasındaki kalibrasyon gürültüsü değişimine uyum sağlar.
NORMAL_P99_GURULTU_ORANI_ESIGI = 2.15
NORMAL_MAKS_GURULTU_ORANI_ESIGI = 2.35
NORMAL_AKTIF_1PX_ORANI_ESIGI = 0.035
REFERANS_BANT_RENK_MESAFESI_ESIGI = 8.0
KALIBRASYON_GURULTU_P95_ESIGI = 2.0
KALIBRASYON_LAZER_GUCU_ESIGI = 10.0

# Rijit A4 kalibrasyonundaki 1,70 px sınırı gerçek kumaşın doğal dalgasını
# kusur saydığı için 21.08.2026 tarihli tekrarlı canlı deneyle güncellendi.
# Aynı yerleşimde beş düz ölçüm 2,15-2,41 px, beş çapraz sırt ölçümü ise
# 2,71-3,05 px aralığında kaldı. 2,60 px iki grup arasındaki güvenli boşluktur.
YUKSEKLIK_KUSUR_SAPMA_ARALIK_ESIGI = 2.60
YUKSEKLIK_KUSUR_AKTIF_ORAN_ESIGI = 0.20
# Yükselti kapısını geçmeyen örneklerde düşük p95, yüzeyde yerel ve belirgin
# bir şekil bozukluğu olmadığını gösterir. Bu iki koşul canlı RF'nin düz
# kumaşa verdiği hatalı yüksek skoru bastırmak için birlikte kullanılır.
CANLI_NORMAL_SAPMA_ARALIK_ESIGI = 2.60
CANLI_NORMAL_SAPMA_P95_ESIGI = 1.15
YUKSEKLIK_MM_KESME = -3.07
YUKSEKLIK_MM_EGIM = 3.27


def rgb_oku(dosya: Path) -> np.ndarray:
    with Image.open(dosya) as goruntu:
        rgb = np.asarray(goruntu.convert("RGB"), dtype=np.float32)
    if rgb.shape[0] < Y1 or rgb.shape[1] < X1:
        raise ValueError(
            f"Görüntü çözünürlüğü yetersiz: {dosya} -> {rgb.shape[1]}x{rgb.shape[0]}"
        )
    return rgb


def lazer_izini_bul(acik: np.ndarray, kapali: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    fark = acik - kapali
    skor = fark[..., 0] - 0.55 * fark[..., 1] - 0.45 * fark[..., 2]
    roi = skor[Y0:Y1, X0:X1]
    yumusatilmis = (
        np.roll(roi, -2, axis=0)
        + 2 * np.roll(roi, -1, axis=0)
        + 3 * roi
        + 2 * np.roll(roi, 1, axis=0)
        + np.roll(roi, 2, axis=0)
    ) / 9.0
    tepeler = np.argmax(yumusatilmis, axis=0)
    iz = np.empty(yumusatilmis.shape[1], dtype=float)
    guc = np.empty(yumusatilmis.shape[1], dtype=float)
    for sutun, tepe in enumerate(tepeler):
        alt = max(0, tepe - 6)
        ust = min(yumusatilmis.shape[0], tepe + 7)
        degerler = yumusatilmis[alt:ust, sutun]
        taban = np.percentile(yumusatilmis[:, sutun], 65)
        agirliklar = np.clip(degerler - taban, 0, None)
        if agirliklar.sum() > 1e-6:
            iz[sutun] = Y0 + np.sum(
                (np.arange(alt, ust) + 0.5) * agirliklar
            ) / agirliklar.sum()
        else:
            iz[sutun] = Y0 + tepe
        guc[sutun] = yumusatilmis[tepe, sutun] - np.median(
            yumusatilmis[:, sutun]
        )
    return iz, guc


def egimi_cikar(iz: np.ndarray) -> np.ndarray:
    x = np.arange(X0, X1)
    referans = (
        ((x >= REFERANS_SOL[0]) & (x <= REFERANS_SOL[1]))
        | ((x >= REFERANS_SAG[0]) & (x <= REFERANS_SAG[1]))
    )
    katsayilar = np.polyfit(x[referans], iz[referans], 1)
    return iz - np.polyval(katsayilar, x)


def en_uzun_seri(maske: np.ndarray) -> int:
    en_uzun = mevcut = 0
    for deger in maske:
        mevcut = mevcut + 1 if deger else 0
        en_uzun = max(en_uzun, mevcut)
    return en_uzun


def goruntu_ciftini_isle(acik: Path, kapali: Path) -> tuple[np.ndarray, np.ndarray]:
    iz, guc = lazer_izini_bul(rgb_oku(acik), rgb_oku(kapali))
    return egimi_cikar(iz), guc


def goruntu_ciftlerini_isle(
    aciklar: list[Path],
    kapalilar: list[Path],
) -> tuple[np.ndarray, np.ndarray]:
    """Tek kare gürültüsünü azaltmak için tekrarların medyan profilini döndürür."""
    if len(aciklar) != len(kapalilar):
        raise ValueError("Lazer açık ve kapalı görüntü sayıları eşit olmalı.")
    if not aciklar:
        raise ValueError("En az bir lazer açık/kapalı görüntü çifti gerekli.")
    izler = []
    gucler = []
    for acik, kapali in zip(aciklar, kapalilar):
        iz, guc = goruntu_ciftini_isle(acik, kapali)
        izler.append(iz)
        gucler.append(guc)
    return (
        np.median(np.stack(izler), axis=0),
        np.median(np.stack(gucler), axis=0),
    )


def kalibrasyonu_oku(
    klasor: Path,
) -> tuple[np.ndarray, np.ndarray, float, float]:
    izler = []
    gucler = []
    sol_bant_renkleri = []
    sag_bant_renkleri = []
    for tekrar in range(1, 4):
        acik = klasor / f"D00_A_{tekrar:02d}.jpg"
        kapali = klasor / f"D00_K_{tekrar:02d}.jpg"
        if not acik.is_file() or not kapali.is_file():
            raise FileNotFoundError(f"Kalibrasyon çifti eksik: {acik.name} / {kapali.name}")
        iz, guc = goruntu_ciftini_isle(acik, kapali)
        izler.append(iz)
        gucler.append(guc)
        kapali_rgb = rgb_oku(kapali)
        sol_bant_renkleri.append(
            np.median(
                kapali_rgb[Y0:Y1, REFERANS_SOL[0]:REFERANS_SOL[1] + 1],
                axis=(0, 1),
            )
        )
        sag_bant_renkleri.append(
            np.median(
                kapali_rgb[Y0:Y1, REFERANS_SAG[0]:REFERANS_SAG[1] + 1],
                axis=(0, 1),
            )
        )

    referans_iz = np.median(np.stack(izler), axis=0)
    referans_guc = np.median(np.stack(gucler), axis=0)
    x = np.arange(X0, X1)
    analiz = (x >= ANALIZ_SOL) & (x <= ANALIZ_SAG)
    hatalar = []
    for iz in izler:
        hatalar.extend(np.abs(iz[analiz] - referans_iz[analiz]).tolist())
    gurultu_p95 = float(np.percentile(np.asarray(hatalar), 95))
    sol_renk = np.median(np.stack(sol_bant_renkleri), axis=0)
    sag_renk = np.median(np.stack(sag_bant_renkleri), axis=0)
    bant_renk_mesafesi = float(np.linalg.norm(sol_renk - sag_renk))
    return referans_iz, referans_guc, gurultu_p95, bant_renk_mesafesi


def kalibrasyon_sorunlarini_bul(
    referans_guc: np.ndarray,
    gurultu_p95: float,
    bant_renk_mesafesi: float,
) -> tuple[list[str], float]:
    """Kalibrasyonun ölçüm üretmeye uygun olup olmadığını denetler."""
    x = np.arange(X0, X1)
    analiz = (x >= ANALIZ_SOL) & (x <= ANALIZ_SAG)
    lazer_gucu_medyan = float(np.median(referans_guc[analiz]))
    sorunlar = []
    if bant_renk_mesafesi > REFERANS_BANT_RENK_MESAFESI_ESIGI:
        sorunlar.append("iki referans bandı aynı kumaş yüzeyi üzerinde değil")
    if gurultu_p95 > KALIBRASYON_GURULTU_P95_ESIGI:
        sorunlar.append("kalibrasyon profilleri birbiriyle tutarsız")
    if lazer_gucu_medyan < KALIBRASYON_LAZER_GUCU_ESIGI:
        sorunlar.append("kalibrasyonda lazer açık görüntüleri algılanamadı")
    return sorunlar, lazer_gucu_medyan


def ozellikleri_cikar(
    iz: np.ndarray,
    guc: np.ndarray,
    referans_iz: np.ndarray,
    referans_guc: np.ndarray,
    gurultu_p95: float,
) -> dict[str, float]:
    x = np.arange(X0, X1)
    analiz = (x >= ANALIZ_SOL) & (x <= ANALIZ_SAG)
    fark_tumu = (iz - referans_iz)[analiz]
    sinyal_tumu = guc[analiz]
    referans_sinyal = referans_guc[analiz]
    gorunurluk_esigi = max(3.0, 0.25 * float(np.median(referans_sinyal)))
    referans_gecerli = referans_sinyal >= gorunurluk_esigi
    olcum_gecerli = sinyal_tumu >= gorunurluk_esigi
    gecerli = referans_gecerli & olcum_gecerli
    if int(np.sum(gecerli)) < 25:
        gecerli = np.ones_like(referans_gecerli, dtype=bool)

    fark = fark_tumu[gecerli]
    sinyal = sinyal_tumu[gecerli]
    mutlak = np.abs(fark)
    egim = np.abs(np.diff(fark))
    egrilik = np.abs(np.diff(fark, n=2))
    return {
        "sapma_medyan_px": float(np.median(mutlak)),
        "sapma_p90_px": float(np.percentile(mutlak, 90)),
        "sapma_p95_px": float(np.percentile(mutlak, 95)),
        "sapma_p99_px": float(np.percentile(mutlak, 99)),
        "sapma_maks_px": float(np.max(mutlak)),
        "sapma_std_px": float(np.std(fark)),
        "sapma_aralik_px": float(np.ptp(fark)),
        "egim_medyan_px": float(np.median(egim)),
        "egim_p95_px": float(np.percentile(egim, 95)),
        "egim_maks_px": float(np.max(egim)),
        "egrilik_p95_px": float(np.percentile(egrilik, 95)),
        "aktif_oran_0_5px": float(np.mean(mutlak >= 0.5)),
        "aktif_oran_1px": float(np.mean(mutlak >= 1.0)),
        "aktif_oran_2px": float(np.mean(mutlak >= 2.0)),
        "aktif_oran_5px": float(np.mean(mutlak >= 5.0)),
        "en_uzun_aktif_seri_1px": float(en_uzun_seri(mutlak >= 1.0)),
        "lazer_gucu_medyan": float(np.median(sinyal)),
        "lazer_gucu_p10": float(np.percentile(sinyal, 10)),
        "lazer_gucu_std": float(np.std(sinyal)),
        "zayif_lazer_orani_3": float(np.mean(sinyal < 3.0)),
        "zayif_lazer_orani_5": float(np.mean(sinyal < 5.0)),
        "zayif_lazer_orani_10": float(np.mean(sinyal < 10.0)),
        "referans_gurultu_p95_px": float(gurultu_p95),
        "sapma_p95_gurultu_orani": float(
            np.percentile(mutlak, 95) / max(gurultu_p95, 0.1)
        ),
        "sapma_p99_gurultu_orani": float(
            np.percentile(mutlak, 99) / max(gurultu_p95, 0.1)
        ),
        "sapma_maks_gurultu_orani": float(
            np.max(mutlak) / max(gurultu_p95, 0.1)
        ),
        "gurultu_ustu_aktif_oran": float(
            np.mean(mutlak >= max(0.5, 3.0 * gurultu_p95))
        ),
        "lazer_kayip_orani": float(
            np.sum(referans_gecerli & ~olcum_gecerli)
            / max(1, np.sum(referans_gecerli))
        ),
    }


def main() -> None:
    betik_klasoru = Path(__file__).resolve().parent
    yeni_model = betik_klasoru / "wp8_random_forest_canli.joblib"
    yeni_bilgi = betik_klasoru / "wp8_model_bilgileri_canli.json"
    parser = argparse.ArgumentParser()
    parser.add_argument("--kalibrasyon", type=Path, required=True)
    parser.add_argument("--kalibrasyon-kontrol", action="store_true")
    parser.add_argument("--lazer-acik", type=Path, nargs="+")
    parser.add_argument("--lazer-kapali", type=Path, nargs="+")
    parser.add_argument(
        "--model",
        type=Path,
        default=(
            yeni_model
            if yeni_model.is_file()
            else betik_klasoru / "wp7_random_forest_degerlendirme.joblib"
        ),
    )
    parser.add_argument(
        "--bilgi",
        type=Path,
        default=(
            yeni_bilgi
            if yeni_bilgi.is_file()
            else betik_klasoru / "wp7_model_bilgileri.json"
        ),
    )
    parser.add_argument("--cikti", type=Path)
    parser.add_argument("--gercek-kod", default="bilinmiyor")
    parser.add_argument("--gercek-etiket", default="bilinmiyor")
    parser.add_argument("--ozet-csv", type=Path)
    args = parser.parse_args()

    baslangic = time.perf_counter()
    referans_iz, referans_guc, gurultu, bant_renk_mesafesi = kalibrasyonu_oku(
        args.kalibrasyon
    )
    kalibrasyon_sorunlari, kalibrasyon_lazer_gucu = kalibrasyon_sorunlarini_bul(
        referans_guc,
        gurultu,
        bant_renk_mesafesi,
    )
    if args.kalibrasyon_kontrol:
        print("Kalibrasyon gürültüsü p95:", f"{gurultu:.4f} px")
        print("Kalibrasyon lazer gücü medyanı:", f"{kalibrasyon_lazer_gucu:.2f}")
        print("Referans bant renk mesafesi:", f"{bant_renk_mesafesi:.2f}")
        if kalibrasyon_sorunlari:
            print("KALIBRASYON GECERSIZ:", "; ".join(kalibrasyon_sorunlari))
            raise SystemExit(2)
        print("Kalibrasyon geçerli. Canlı ölçümlere başlanabilir.")
        return

    if not args.lazer_acik or not args.lazer_kapali or args.cikti is None:
        parser.error(
            "Canlı tahmin için --lazer-acik, --lazer-kapali ve --cikti gereklidir."
        )

    from joblib import load

    bilgi = json.loads(args.bilgi.read_text(encoding="utf-8"))
    ozellik_sirasi = bilgi["feature_columns"]
    model = load(args.model)
    iz, guc = goruntu_ciftlerini_isle(args.lazer_acik, args.lazer_kapali)
    ozellikler = ozellikleri_cikar(
        iz, guc, referans_iz, referans_guc, gurultu
    )
    eksik = [ad for ad in ozellik_sirasi if ad not in ozellikler]
    if eksik:
        raise ValueError("Eksik özellik: " + ", ".join(eksik))
    X = np.asarray([[ozellikler[ad] for ad in ozellik_sirasi]], dtype=float)
    if int(model.n_features_in_) != X.shape[1]:
        raise ValueError("Model ile özellik sayısı uyuşmuyor.")

    kalite_sorunlari = list(kalibrasyon_sorunlari)
    if len(args.lazer_acik) != 3:
        kalite_sorunlari.append("canlı ölçüm üç görüntü çifti içermiyor")
    if ozellikler["lazer_kayip_orani"] > 0.50:
        kalite_sorunlari.append("lazer açık/kapalı çifti ayırt edilemiyor")
    if ozellikler["lazer_gucu_medyan"] < 10.0:
        kalite_sorunlari.append("lazer sinyali çok zayıf")
    olcum_gecerli = not kalite_sorunlari

    rf_tahmin = None
    rf_kusur_skoru = None
    normal_kapisi = False
    canli_normal_kapisi = False
    yukseklik_kapisi = False
    tahmini_yukseklik_mm = max(
        0.0,
        YUKSEKLIK_MM_KESME
        + YUKSEKLIK_MM_EGIM * ozellikler["sapma_aralik_px"],
    )
    canli_model = str(bilgi.get("veri_surumu", "")).startswith(
        "WP8 canlı üçlü çekim"
    )
    normal_geometri_kapisi_etkin = bool(
        bilgi.get("normal_geometri_kapisi", True)
    )
    if olcum_gecerli:
        rf_tahmin = int(model.predict(X)[0])
        rf_kusur_skoru = float(model.predict_proba(X)[0, 1])
        yukseklik_kapisi = (
            ozellikler["sapma_aralik_px"]
            >= YUKSEKLIK_KUSUR_SAPMA_ARALIK_ESIGI
            and ozellikler["aktif_oran_0_5px"]
            >= YUKSEKLIK_KUSUR_AKTIF_ORAN_ESIGI
        )
        normal_kapisi = (not canli_model) and (
            ozellikler["sapma_p99_gurultu_orani"]
            < NORMAL_P99_GURULTU_ORANI_ESIGI
            and ozellikler["sapma_maks_gurultu_orani"]
            < NORMAL_MAKS_GURULTU_ORANI_ESIGI
            and ozellikler["aktif_oran_1px"] < NORMAL_AKTIF_1PX_ORANI_ESIGI
        )
        canli_normal_kapisi = canli_model and normal_geometri_kapisi_etkin and (
            ozellikler["sapma_aralik_px"]
            < CANLI_NORMAL_SAPMA_ARALIK_ESIGI
            and ozellikler["sapma_p95_px"] < CANLI_NORMAL_SAPMA_P95_ESIGI
        )
        if yukseklik_kapisi:
            tahmin = 1
            tahmin_etiketi = "KUSUR"
            karar_yontemi = "yukseklik_kapisi"
        elif canli_normal_kapisi:
            tahmin = 0
            tahmin_etiketi = "NORMAL"
            karar_yontemi = "canli_normal_geometri_kapisi"
        elif normal_kapisi:
            tahmin = 0
            tahmin_etiketi = "NORMAL"
            karar_yontemi = "gecici_normal_kapisi"
        else:
            tahmin = rf_tahmin
            tahmin_etiketi = "KUSUR" if tahmin else "NORMAL"
            karar_yontemi = (
                "random_forest_canli" if canli_model else "random_forest"
            )
    else:
        tahmin = None
        tahmin_etiketi = "OLCUM_GECERSIZ"
        karar_yontemi = "kalite_kontrolu"
    sure_ms = (time.perf_counter() - baslangic) * 1000.0
    sonuc = {
        "zaman": datetime.now().astimezone().isoformat(),
        "gercek_kod": args.gercek_kod,
        "gercek_etiket": args.gercek_etiket,
        "olcum_gecerli": olcum_gecerli,
        "gecersizlik_nedeni": "; ".join(kalite_sorunlari) if kalite_sorunlari else None,
        "tahmin_sinif": tahmin,
        "tahmin_etiketi": tahmin_etiketi,
        "karar_yontemi": karar_yontemi,
        "tekrar_sayisi": len(args.lazer_acik),
        "normal_kapisi_saglandi": normal_kapisi,
        "canli_normal_kapisi_saglandi": canli_normal_kapisi,
        "canli_normal_kapisi_etkin": normal_geometri_kapisi_etkin,
        "yukseklik_kapisi_saglandi": yukseklik_kapisi,
        "geometrik_sapma_araligi_px": ozellikler["sapma_aralik_px"],
        "tahmini_yukseklik_mm": tahmini_yukseklik_mm,
        "yukseklik_sapma_aralik_esigi_px": (
            YUKSEKLIK_KUSUR_SAPMA_ARALIK_ESIGI
        ),
        "yukseklik_aktif_oran_esigi": YUKSEKLIK_KUSUR_AKTIF_ORAN_ESIGI,
        "rf_ham_tahmin_sinif": rf_tahmin,
        "rf_ham_kusur_skoru": rf_kusur_skoru,
        # Geriye uyumluluk için tutulur; bu değer RF'nin ham skorudur.
        "kusur_olasiligi": rf_kusur_skoru,
        "islem_suresi_ms": sure_ms,
        "kalibrasyon_gurultu_p95_px": gurultu,
        "kalibrasyon_lazer_gucu_medyan": kalibrasyon_lazer_gucu,
        "referans_bant_renk_mesafesi": bant_renk_mesafesi,
        "lazer_acik": [str(dosya) for dosya in args.lazer_acik],
        "lazer_kapali": [str(dosya) for dosya in args.lazer_kapali],
        "ozellikler": ozellikler,
    }
    args.cikti.parent.mkdir(parents=True, exist_ok=True)
    args.cikti.write_text(
        json.dumps(sonuc, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    if args.ozet_csv is not None:
        args.ozet_csv.parent.mkdir(parents=True, exist_ok=True)
        yeni_dosya = not args.ozet_csv.exists()
        with args.ozet_csv.open("a", encoding="utf-8-sig", newline="") as hedef:
            alanlar = [
                "zaman",
                "olcum",
                "gercek_kod",
                "gercek_etiket",
                "olcum_gecerli",
                "gecersizlik_nedeni",
                "tahmin_sinif",
                "tahmin_etiketi",
                "karar_yontemi",
                "tekrar_sayisi",
                "normal_kapisi_saglandi",
                "canli_normal_kapisi_saglandi",
                "yukseklik_kapisi_saglandi",
                "geometrik_sapma_araligi_px",
                "tahmini_yukseklik_mm",
                "kusur_olasiligi",
                "islem_suresi_ms",
                "kalibrasyon_gurultu_p95_px",
                "kalibrasyon_lazer_gucu_medyan",
                "referans_bant_renk_mesafesi",
                "sapma_std_px",
                "sapma_medyan_px",
                "sapma_p95_px",
                "sapma_p99_gurultu_orani",
                "sapma_maks_gurultu_orani",
                "aktif_oran_0_5px",
                "aktif_oran_1px",
                "lazer_gucu_std",
                "lazer_kayip_orani",
            ]
            yazici = csv.DictWriter(hedef, fieldnames=alanlar)
            if yeni_dosya:
                yazici.writeheader()
            yazici.writerow(
                {
                    "zaman": sonuc["zaman"],
                    "olcum": args.cikti.stem.replace("_sonuc", ""),
                    "gercek_kod": args.gercek_kod,
                    "gercek_etiket": args.gercek_etiket,
                    "olcum_gecerli": int(olcum_gecerli),
                    "gecersizlik_nedeni": sonuc["gecersizlik_nedeni"] or "",
                    "tahmin_sinif": tahmin,
                    "tahmin_etiketi": sonuc["tahmin_etiketi"],
                    "karar_yontemi": karar_yontemi,
                    "tekrar_sayisi": len(args.lazer_acik),
                    "normal_kapisi_saglandi": int(normal_kapisi),
                    "canli_normal_kapisi_saglandi": int(canli_normal_kapisi),
                    "yukseklik_kapisi_saglandi": int(yukseklik_kapisi),
                    "geometrik_sapma_araligi_px": (
                        f"{ozellikler['sapma_aralik_px']:.6f}"
                    ),
                    "tahmini_yukseklik_mm": f"{tahmini_yukseklik_mm:.4f}",
                    "kusur_olasiligi": "" if rf_kusur_skoru is None else f"{rf_kusur_skoru:.6f}",
                    "islem_suresi_ms": f"{sure_ms:.3f}",
                    "kalibrasyon_gurultu_p95_px": f"{gurultu:.6f}",
                    "kalibrasyon_lazer_gucu_medyan": f"{kalibrasyon_lazer_gucu:.6f}",
                    "referans_bant_renk_mesafesi": f"{bant_renk_mesafesi:.6f}",
                    "sapma_std_px": f"{ozellikler['sapma_std_px']:.6f}",
                    "sapma_medyan_px": f"{ozellikler['sapma_medyan_px']:.6f}",
                    "sapma_p95_px": f"{ozellikler['sapma_p95_px']:.6f}",
                    "sapma_p99_gurultu_orani": f"{ozellikler['sapma_p99_gurultu_orani']:.6f}",
                    "sapma_maks_gurultu_orani": f"{ozellikler['sapma_maks_gurultu_orani']:.6f}",
                    "aktif_oran_0_5px": f"{ozellikler['aktif_oran_0_5px']:.6f}",
                    "aktif_oran_1px": f"{ozellikler['aktif_oran_1px']:.6f}",
                    "lazer_gucu_std": f"{ozellikler['lazer_gucu_std']:.6f}",
                    "lazer_kayip_orani": f"{ozellikler['lazer_kayip_orani']:.6f}",
                }
            )
    print("Tahmin:", sonuc["tahmin_etiketi"])
    print("Birleştirilen görüntü çifti:", len(args.lazer_acik))
    if olcum_gecerli:
        print("Karar yöntemi:", karar_yontemi)
        print("RF ham kusur skoru:", f"%{rf_kusur_skoru * 100:.2f}")
        print(
            "Geometrik sapma aralığı:",
            f"{ozellikler['sapma_aralik_px']:.2f} px",
        )
        print(
            "Yükseklik kapısı:",
            "SAĞLANDI" if yukseklik_kapisi else "sağlanmadı",
        )
        if normal_kapisi:
            print("Not: Karar, WP8 geçici normal yüzey kapısıyla verildi.")
        if canli_normal_kapisi:
            print("Not: Düşük yerel sapma nedeniyle canlı normal geometri kapısı uygulandı.")
        if yukseklik_kapisi:
            print("Not: Geometrik yükselti tekrarlı canlı testte doğrulanan kusur bölgesinde.")
    else:
        print("Neden:", sonuc["gecersizlik_nedeni"])
        print("Bu ölçümü sınıflandırmaya katmayın; lazer durumlarını düzelterek tekrarlayın.")
    print("İşlem süresi:", f"{sure_ms:.1f} ms")
    print("Kalibrasyon gürültüsü p95:", f"{gurultu:.4f} px")
    print("Kalibrasyon lazer gücü medyanı:", f"{kalibrasyon_lazer_gucu:.2f}")
    print("Referans bant renk mesafesi:", f"{bant_renk_mesafesi:.2f}")
    print("Sonuç dosyası:", args.cikti)


if __name__ == "__main__":
    main()
