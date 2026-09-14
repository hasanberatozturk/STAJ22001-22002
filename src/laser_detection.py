"""Lazer kapalı ve açık iki fotoğraftan kabarıklık sonucunu bulur."""

from dataclasses import dataclass

import cv2
import numpy as np

from .config import (
    LAZER_IKI_KARE_ESIGI,
    LAZER_ISLEM_GENISLIGI,
    LAZER_KESINTISIZ_UZUNLUK,
    LAZER_X_ALANI,
    LAZER_Y_ALANI,
)


@dataclass(frozen=True)
class LazerOlcumu:
    """Bulunan lazer çizgisinin ölçüm bilgilerini tutar."""

    sapma: float
    sinyal: float
    uzunluk_orani: float = 0.0


@dataclass(frozen=True)
class LazerKarsilastirma:
    """İki fotoğraf karşılaştırıldıktan sonra arayüze gönderilen sonuçtur."""

    kabariklik_var: bool
    sapma: float
    sinyal: float
    uzunluk_orani: float
    esik: float
    yon: str


def _cizgi_sapmasi(
    x_degerleri: np.ndarray,
    y_degerleri: np.ndarray,
    en_az_tolerans: float,
) -> float:
    """Lazerin normal eğimini çıkarıp kalan bükülmeyi hesaplar."""
    if len(x_degerleri) < 2:
        raise ValueError("Lazer profili ölçüm için çok kısa.")

    # Lazer kamerada biraz eğik durabilir. Bu eğim kabarıklık olmadığı için çıkarılıyor.
    uygun_noktalar = np.ones_like(x_degerleri, dtype=bool)
    for _ in range(2):
        katsayilar = np.polyfit(
            x_degerleri[uygun_noktalar],
            y_degerleri[uygun_noktalar],
            1,
        )
        farklar = y_degerleri - np.polyval(katsayilar, x_degerleri)
        orta = float(np.median(farklar[uygun_noktalar]))
        dagilim = float(np.median(np.abs(farklar[uygun_noktalar] - orta)))
        tolerans = max(en_az_tolerans, 4.0 * 1.4826 * dagilim)
        yeni_noktalar = np.abs(farklar - orta) <= tolerans
        if int(np.sum(yeni_noktalar)) < 2:
            break
        uygun_noktalar = yeni_noktalar

    katsayilar = np.polyfit(
        x_degerleri[uygun_noktalar],
        y_degerleri[uygun_noktalar],
        1,
    )
    farklar = y_degerleri - np.polyval(katsayilar, x_degerleri)
    return float(np.percentile(farklar, 98) - np.percentile(farklar, 2))


def _medyan_filtresi(degerler: np.ndarray, boyut: int) -> np.ndarray:
    """Çizgideki küçük kamera titreşimlerini azaltır."""
    kenar = boyut // 2
    dolgulu = np.pad(degerler, (kenar, kenar), mode="edge")
    pencereler = np.lib.stride_tricks.sliding_window_view(dolgulu, boyut)
    return np.median(pencereler, axis=1)


def lazer_fotograflarini_karsilastir(
    lazer_kapali_kare: np.ndarray,
    lazer_acik_kare: np.ndarray,
) -> LazerKarsilastirma:
    """Lazer kapalı ve açık fotoğrafı karşılaştırıp sonucu döndürür."""
    if lazer_kapali_kare is None or lazer_acik_kare is None:
        raise ValueError("Karşılaştırma için iki fotoğraf da gereklidir.")
    if lazer_kapali_kare.shape != lazer_acik_kare.shape:
        raise ValueError("İki fotoğrafın görüntü boyutu aynı değil.")

    # İki kare arasındaki kırmızı artış lazer çizgisini ortaya çıkarıyor.
    kapali = lazer_kapali_kare.astype(np.float32)
    acik = lazer_acik_kare.astype(np.float32)
    renk_farki = acik - kapali
    kirmizi_puani = (
        renk_farki[:, :, 2]
        - 0.55 * renk_farki[:, :, 1]
        - 0.45 * renk_farki[:, :, 0]
    )
    kirmizi_puani = np.clip(kirmizi_puani, 0.0, None)

    # Telefon yatay veya dik tutulabildiği için iki yön de deneniyor.
    adaylar: list[tuple[float, str, LazerOlcumu]] = []
    for yon, puan in (
        ("yatay", kirmizi_puani),
        ("dikey", cv2.rotate(kirmizi_puani, cv2.ROTATE_90_CLOCKWISE)),
    ):
        try:
            olcum, kalite = _fark_goruntusunden_lazer_olc(puan)
            adaylar.append((kalite, yon, olcum))
        except ValueError:
            continue

    if not adaylar:
        raise ValueError(
            "Lazer çizgisi okunamadı. Kamerayı sabit tutup lazeri açtıktan sonra "
            "bir saniye bekleyerek fotoğrafı tekrar alın."
        )

    _, lazer_yonu, olcum = max(adaylar, key=lambda aday: aday[0])
    return LazerKarsilastirma(
        kabariklik_var=olcum.sapma >= LAZER_IKI_KARE_ESIGI,
        sapma=olcum.sapma,
        sinyal=olcum.sinyal,
        uzunluk_orani=olcum.uzunluk_orani,
        esik=LAZER_IKI_KARE_ESIGI,
        yon=lazer_yonu,
    )


def _fark_goruntusunden_lazer_olc(
    kirmizi_puani: np.ndarray,
) -> tuple[LazerOlcumu, float]:
    """Kırmızı fark görüntüsünden lazer çizgisinin orta noktalarını çıkarır."""
    ilk_yukseklik, ilk_genislik = kirmizi_puani.shape
    if ilk_genislik > LAZER_ISLEM_GENISLIGI:
        islem_genisligi = LAZER_ISLEM_GENISLIGI
        islem_yuksekligi = round(
            ilk_yukseklik * islem_genisligi / ilk_genislik
        )
        kirmizi_puani = cv2.resize(
            kirmizi_puani,
            (islem_genisligi, islem_yuksekligi),
            interpolation=cv2.INTER_AREA,
        )

    yukseklik_olcegi = ilk_yukseklik / kirmizi_puani.shape[0]
    yukseklik, genislik = kirmizi_puani.shape
    x0 = int(genislik * LAZER_X_ALANI[0])
    x1 = int(genislik * LAZER_X_ALANI[1])
    y0 = int(yukseklik * LAZER_Y_ALANI[0])
    y1 = int(yukseklik * LAZER_Y_ALANI[1])
    alan = kirmizi_puani[y0:y1, x0:x1]
    if alan.shape[0] < 20 or alan.shape[1] < 40:
        raise ValueError("Lazer için bakılan görüntü alanı çok küçük.")

    # Her sütundaki en güçlü kırmızı bölge lazer için aday kabul ediliyor.
    yumusatilmis = cv2.GaussianBlur(alan, (1, 5), 0)
    tepe_satirlari = np.argmax(yumusatilmis, axis=0)
    taban = np.percentile(yumusatilmis, 65, axis=0)
    tepe_gucu = np.max(yumusatilmis, axis=0) - taban

    guclu_deger = float(np.percentile(tepe_gucu, 80))
    sinyal_esigi = max(8.0, min(35.0, guclu_deger * 0.25))
    gecerli = tepe_gucu >= sinyal_esigi
    gecerli_sutunlar = np.flatnonzero(gecerli)
    if len(gecerli_sutunlar) < 40:
        raise ValueError("Lazer sinyali yeterince güçlü değil.")

    ilk_sutun = int(gecerli_sutunlar[0])
    son_sutun = int(gecerli_sutunlar[-1])
    uzunluk_orani = (son_sutun - ilk_sutun + 1) / alan.shape[1]
    doluluk_orani = len(gecerli_sutunlar) / max(1, son_sutun - ilk_sutun + 1)
    if uzunluk_orani < LAZER_KESINTISIZ_UZUNLUK or doluluk_orani < 0.30:
        raise ValueError("Uzun bir lazer çizgisi bulunamadı.")

    # Lazer kalın görünse bile çizginin ortasını bulmak için ağırlıklı ortalama alınıyor.
    merkezler = np.full(alan.shape[1], np.nan, dtype=np.float64)
    pencere = max(5, round(alan.shape[0] * 0.025))
    for sutun in gecerli_sutunlar:
        tepe = int(tepe_satirlari[sutun])
        alt = max(0, tepe - pencere)
        ust = min(alan.shape[0], tepe + pencere + 1)
        degerler = yumusatilmis[alt:ust, sutun]
        agirliklar = np.clip(degerler - taban[sutun], 0.0, None)
        if float(np.sum(agirliklar)) > 1e-6:
            satirlar = np.arange(alt, ust, dtype=np.float64)
            merkezler[sutun] = float(np.average(satirlar, weights=agirliklar))

    kullanilan = np.flatnonzero(np.isfinite(merkezler))
    if len(kullanilan) < 40:
        raise ValueError("Lazer çizgisinin merkezi hesaplanamadı.")

    # Kısa boşluklar tamamlanıyor ve küçük titreşimler temizleniyor.
    x = np.arange(kullanilan[0], kullanilan[-1] + 1, dtype=np.float64)
    y = np.interp(x, kullanilan, merkezler[kullanilan])
    filtre_boyutu = min(11, len(y) if len(y) % 2 else len(y) - 1)
    if filtre_boyutu >= 3:
        y = _medyan_filtresi(y, filtre_boyutu)

    sapma = _cizgi_sapmasi(x, y, en_az_tolerans=2.0) * yukseklik_olcegi
    sinyal = float(np.median(tepe_gucu[gecerli]))
    # Kalite puanı yalnız yatay ve dikey adaylardan daha iyi olanı seçmek için kullanılıyor.
    kalite = uzunluk_orani * doluluk_orani * max(sinyal, 1.0)
    return (
        LazerOlcumu(
            sapma=sapma,
            sinyal=sinyal,
            uzunluk_orani=float(uzunluk_orani),
        ),
        float(kalite),
    )
