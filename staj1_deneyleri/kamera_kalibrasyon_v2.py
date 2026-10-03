"""Satranç deseni görüntülerinden kamera parametrelerini ve hata değerlerini hesaplar."""

from __future__ import annotations

import argparse
import glob
from datetime import datetime
import sys
from pathlib import Path

import cv2
import numpy as np


# Güvenilir bir çözüm için farklı açılardan en az sekiz geçerli görüntü gerekir.
ASGARI_GECERLI_GORUNTU = 8


def nesne_noktalari_olustur(ic_kose_sayisi, kare_boyutu_mm) -> np.ndarray:
    """Desendeki iç köşelerin düzlem üzerindeki konumlarını milimetre cinsinden oluşturur."""
    noktalar = np.zeros(
        (ic_kose_sayisi[0] * ic_kose_sayisi[1], 3), dtype=np.float32
    )
    noktalar[:, :2] = np.mgrid[
        0 : ic_kose_sayisi[0], 0 : ic_kose_sayisi[1]
    ].T.reshape(-1, 2)
    noktalar *= kare_boyutu_mm
    return noktalar


def koseleri_bul(gri: np.ndarray, ic_kose_sayisi) -> tuple[bool, np.ndarray | None, str]:
    """İç köşeleri bulur; ilk yöntem başarısızsa klasik yöntemi dener."""
    sb_bayraklari = (
        cv2.CALIB_CB_NORMALIZE_IMAGE
        | cv2.CALIB_CB_EXHAUSTIVE
        | cv2.CALIB_CB_ACCURACY
    )

    if hasattr(cv2, "findChessboardCornersSB"):
        bulundu, koseler = cv2.findChessboardCornersSB(
            gri, ic_kose_sayisi, flags=sb_bayraklari
        )
        if bulundu:
            return True, koseler.astype(np.float32), "SB"

    klasik_bayraklar = (
        cv2.CALIB_CB_ADAPTIVE_THRESH
        | cv2.CALIB_CB_NORMALIZE_IMAGE
        | cv2.CALIB_CB_FAST_CHECK
    )
    bulundu, koseler = cv2.findChessboardCorners(
        gri, ic_kose_sayisi, flags=klasik_bayraklar
    )
    if not bulundu:
        return False, None, "-"

    durma_kriteri = (
        cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER,
        50,
        0.001,
    )
    koseler = cv2.cornerSubPix(
        gri, koseler, (11, 11), (-1, -1), durma_kriteri
    )
    return True, koseler, "klasik"


def yaml_kaydet(
    yol: Path,
    kamera_matrisi: np.ndarray,
    distorsiyon: np.ndarray,
    rms: float,
    goruntu_boyutu: tuple[int, int],
    ic_kose_sayisi,
    kare_boyutu_mm,
) -> None:
    depolama = cv2.FileStorage(str(yol), cv2.FILE_STORAGE_WRITE)
    if not depolama.isOpened():
        raise RuntimeError(f"YAML dosyası açılamadı: {yol}")

    depolama.write("kamera_matrisi", kamera_matrisi)
    depolama.write("distorsiyon_katsayilari", distorsiyon)
    depolama.write("rms_hatasi", float(rms))
    depolama.write("goruntu_genisligi", int(goruntu_boyutu[0]))
    depolama.write("goruntu_yuksekligi", int(goruntu_boyutu[1]))
    depolama.write("ic_kose_sutun", int(ic_kose_sayisi[0]))
    depolama.write("ic_kose_satir", int(ic_kose_sayisi[1]))
    depolama.write("kare_boyutu_mm", float(kare_boyutu_mm))
    depolama.release()


def ana_program(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Checkerboard görüntülerinden kamera kalibrasyonu.")
    parser.add_argument("--girdi", type=Path, required=True, help="CALv2_*.jpg dosyalarının klasörü")
    parser.add_argument("--cikti", type=Path, help="Yeni sonuç klasörü; varsa üzerine yazılmaz")
    # Kare sayısı değil, desenin iç köşe sayısı girilmelidir.
    parser.add_argument("--ic-kose", type=int, nargs=2, required=True, metavar=("SUTUN", "SATIR"),
                        help="Kare değil, iç köşe sayısı. Örnek: 9 7")
    parser.add_argument("--kare-mm", type=float, default=20.0, help="Bir karenin kenarı, mm")
    args = parser.parse_args(argv)
    if min(args.ic_kose) < 2 or not np.isfinite(args.kare_mm) or args.kare_mm <= 0:
        parser.error("İç köşe sayıları en az 2, kare boyutu pozitif ve sonlu olmalı.")
    if not args.girdi.is_dir():
        parser.error("Girdi klasörü bulunamadı.")
    girdi_klasoru = args.girdi.resolve()
    ic_kose_sayisi = tuple(args.ic_kose)
    kare_boyutu_mm = args.kare_mm
    cikti_klasoru = args.cikti or (
        Path(__file__).resolve().parents[1] / "output" / "staj1" /
        ("kalibrasyon_" + datetime.now().strftime("%Y%m%d_%H%M%S_%f"))
    )
    if cikti_klasoru.exists():
        parser.error("Çıktı klasörü zaten var; yeni bir klasör belirtin.")
    kose_goruntuleri_klasoru = cikti_klasoru / "kose_tespitleri"

    dosyalar = sorted(
        Path(yol)
        for yol in glob.glob(str(girdi_klasoru / "CALv2_*.jpg"))
    )

    print("\n=== KAMERA KALİBRASYONU V2 ===")
    print(f"Girdi klasörü : {girdi_klasoru}")
    print(f"Bulunan dosya : {len(dosyalar)}")

    if not dosyalar:
        print("HATA: Kalibrasyon görüntüsü bulunamadı.", file=sys.stderr)
        return 1

    cikti_klasoru.mkdir(parents=True, exist_ok=False)
    kose_goruntuleri_klasoru.mkdir()
    sabit_nesne_noktalari = nesne_noktalari_olustur(ic_kose_sayisi, kare_boyutu_mm)
    tum_nesne_noktalari: list[np.ndarray] = []
    tum_goruntu_noktalari: list[np.ndarray] = []
    gecerli_dosyalar: list[Path] = []
    goruntu_boyutu: tuple[int, int] | None = None

    for sira, dosya in enumerate(dosyalar, start=1):
        goruntu = cv2.imread(str(dosya), cv2.IMREAD_COLOR)
        if goruntu is None:
            print(f"[{sira:02d}] OKUNAMADI : {dosya.name}")
            continue

        mevcut_boyut = (goruntu.shape[1], goruntu.shape[0])
        if goruntu_boyutu is None:
            goruntu_boyutu = mevcut_boyut
        elif mevcut_boyut != goruntu_boyutu:
            print(
                f"[{sira:02d}] BOYUT FARKLI: {dosya.name} "
                f"{mevcut_boyut} != {goruntu_boyutu}"
            )
            continue

        gri = cv2.cvtColor(goruntu, cv2.COLOR_BGR2GRAY)
        bulundu, koseler, yontem = koseleri_bul(gri, ic_kose_sayisi)

        if not bulundu or koseler is None:
            print(f"[{sira:02d}] KÖŞE BULUNAMADI: {dosya.name}")
            continue

        tum_nesne_noktalari.append(sabit_nesne_noktalari.copy())
        tum_goruntu_noktalari.append(koseler)
        gecerli_dosyalar.append(dosya)

        isaretli = goruntu.copy()
        cv2.drawChessboardCorners(isaretli, ic_kose_sayisi, koseler, True)
        cv2.imwrite(
            str(kose_goruntuleri_klasoru / dosya.name),
            isaretli,
        )
        print(f"[{sira:02d}] BAŞARILI ({yontem}): {dosya.name}")

    print(
        f"\nKöşesi bulunan görüntü: "
        f"{len(gecerli_dosyalar)} / {len(dosyalar)}"
    )

    if goruntu_boyutu is None:
        print("HATA: Geçerli görüntü boyutu alınamadı.", file=sys.stderr)
        return 1

    if len(gecerli_dosyalar) < ASGARI_GECERLI_GORUNTU:
        print(
            f"HATA: Kalibrasyon için en az {ASGARI_GECERLI_GORUNTU} "
            "geçerli görüntü gerekli.",
            file=sys.stderr,
        )
        return 2

    rms, kamera_matrisi, distorsiyon, donusler, otelemeler = (
        cv2.calibrateCamera(
            tum_nesne_noktalari,
            tum_goruntu_noktalari,
            goruntu_boyutu,
            None,
            None,
        )
    )

    if (
        not np.isfinite(rms)
        or not np.all(np.isfinite(kamera_matrisi))
        or not np.all(np.isfinite(distorsiyon))
        or kamera_matrisi[0, 0] <= 0
        or kamera_matrisi[1, 1] <= 0
    ):
        print("HATA: Geçersiz kalibrasyon sonucu üretildi.", file=sys.stderr)
        return 3

    goruntu_hatalari: list[tuple[str, float]] = []
    toplam_kare_hata = 0.0
    toplam_nokta = 0

    for dosya, nesne, gercek, donus, oteleme in zip(
        gecerli_dosyalar,
        tum_nesne_noktalari,
        tum_goruntu_noktalari,
        donusler,
        otelemeler,
    ):
        tahmin, _ = cv2.projectPoints(
            nesne, donus, oteleme, kamera_matrisi, distorsiyon
        )
        fark = gercek.reshape(-1, 2) - tahmin.reshape(-1, 2)
        kare_hatalar = np.sum(fark * fark, axis=1)
        goruntu_rmse = float(np.sqrt(np.mean(kare_hatalar)))
        goruntu_hatalari.append((dosya.name, goruntu_rmse))
        toplam_kare_hata += float(np.sum(kare_hatalar))
        toplam_nokta += len(kare_hatalar)

    genel_rmse = float(np.sqrt(toplam_kare_hata / toplam_nokta))

    np.save(cikti_klasoru / "kamera_matrisi.npy", kamera_matrisi)
    np.save(cikti_klasoru / "distorsiyon_katsayilari.npy", distorsiyon)
    yaml_kaydet(
        cikti_klasoru / "kamera_parametreleri.yml",
        kamera_matrisi,
        distorsiyon,
        float(rms),
        goruntu_boyutu,
        ic_kose_sayisi,
        kare_boyutu_mm,
    )

    referans_dosya = gecerli_dosyalar[0]
    for aday in gecerli_dosyalar:
        if aday.name == "CALv2_01_merkez.jpg":
            referans_dosya = aday
            break

    referans = cv2.imread(str(referans_dosya), cv2.IMREAD_COLOR)
    yeni_matris, roi = cv2.getOptimalNewCameraMatrix(
        kamera_matrisi,
        distorsiyon,
        goruntu_boyutu,
        0,
        goruntu_boyutu,
    )
    duzeltilmis_tam = cv2.undistort(
        referans, kamera_matrisi, distorsiyon, None, yeni_matris
    )
    cv2.imwrite(
        str(cikti_klasoru / "CALv2_01_merkez_duzeltilmis_tam.jpg"),
        duzeltilmis_tam,
    )

    x, y, genislik, yukseklik = roi
    if genislik > 0 and yukseklik > 0:
        kirpilmis = duzeltilmis_tam[
            y : y + yukseklik, x : x + genislik
        ]
        kirpilmis = cv2.resize(kirpilmis, goruntu_boyutu)
    else:
        kirpilmis = duzeltilmis_tam

    cv2.imwrite(
        str(cikti_klasoru / "CALv2_01_merkez_duzeltilmis.jpg"),
        kirpilmis,
    )
    karsilastirma = np.hstack((referans, kirpilmis))
    cv2.imwrite(
        str(cikti_klasoru / "CALv2_01_once_sonra.jpg"),
        karsilastirma,
    )

    rapor_yolu = cikti_klasoru / "kalibrasyon_raporu.txt"
    with rapor_yolu.open("w", encoding="utf-8") as rapor:
        rapor.write("KAMERA KALİBRASYONU V2 RAPORU\n")
        rapor.write("=" * 40 + "\n")
        rapor.write(f"Toplam görüntü: {len(dosyalar)}\n")
        rapor.write(f"Geçerli görüntü: {len(gecerli_dosyalar)}\n")
        rapor.write(f"Görüntü boyutu: {goruntu_boyutu}\n")
        rapor.write(f"İç köşe sayısı: {ic_kose_sayisi}\n")
        rapor.write(f"Kare boyutu: {kare_boyutu_mm:.1f} mm\n")
        rapor.write(f"OpenCV RMS: {float(rms):.6f} piksel\n")
        rapor.write(f"Genel reprojeksiyon RMSE: {genel_rmse:.6f} piksel\n\n")
        rapor.write("Kamera matrisi:\n")
        rapor.write(np.array2string(kamera_matrisi, precision=10))
        rapor.write("\n\nDistorsiyon katsayıları:\n")
        rapor.write(np.array2string(distorsiyon, precision=10))
        rapor.write("\n\nGörüntü başına reprojeksiyon RMSE:\n")
        for ad, hata in goruntu_hatalari:
            rapor.write(f"{ad}: {hata:.6f} piksel\n")

    print("\n=== KALİBRASYON TAMAMLANDI ===")
    print(f"OpenCV RMS              : {float(rms):.6f} piksel")
    print(f"Reprojeksiyon RMSE      : {genel_rmse:.6f} piksel")
    print(f"Kamera matrisi:\n{kamera_matrisi}")
    print(f"Distorsiyon katsayıları:\n{distorsiyon}")
    print(f"Sonuç klasörü           : {cikti_klasoru}")
    print(f"Rapor                    : {rapor_yolu}")
    return 0


if __name__ == "__main__":
    raise SystemExit(ana_program())
