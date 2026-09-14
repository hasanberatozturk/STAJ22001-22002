"""Kamera görüntüsündeki leke ve yırtıkları kontrol eder."""

from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
from ultralytics import YOLO

from .config import (
    ACIK_KUMAS_PARLAKLIK_SINIRI,
    ACIK_LEKE_EN_BUYUK_ALAN,
    ACIK_LEKE_EN_KUCUK_ALAN,
    ACIK_LEKE_PARLAKLIK_FARKI,
    ACIK_LEKE_RENK_FARKI,
    BIRLIKTE_LEKE_ESIGI,
    DIKEY_GORUNTU_ORANI,
    LEKE_ESIGI,
    LEKE_GORUNTU_BOYUTU,
    LEKE_MODEL_YOLU,
    YIRTIK_ADAY_ESIGI,
    YIRTIK_GORUNTU_BOYUTU,
    YIRTIK_GUCLU_ESIGI,
    YIRTIK_KONTROL_BOYUTLARI,
    YIRTIK_KONTROL_ESIGI,
    YIRTIK_KONTROL_MODEL_YOLU,
    YIRTIK_MODEL_YOLU,
)


@dataclass(frozen=True)
class YirtikKutusu:
    """Yırtık kutusunun dört kenarını ve modelin güven puanını saklar."""

    sol: int
    ust: int
    sag: int
    alt: int
    guven: float


@dataclass(frozen=True)
class GoruntuSonucu:
    """Kamera karesi bittikten sonra arayüze gönderilecek sonuçları saklar."""

    leke_puani: float
    yirtik_puani: float
    leke_var: bool
    yirtik_var: bool
    yirtik_kutulari: tuple[YirtikKutusu, ...] = ()
    yirtik_kontrol_puani: float = 0.0
    yirtik_kontrol_yapildi: bool = False


class KusurTespiti:
    """Leke ve yırtık modellerini çalıştırıp tek bir sonuç hazırlar."""

    def __init__(
        self,
        leke_model_yolu: Path = LEKE_MODEL_YOLU,
        yirtik_model_yolu: Path = YIRTIK_MODEL_YOLU,
        yirtik_kontrol_model_yolu: Path = YIRTIK_KONTROL_MODEL_YOLU,
    ) -> None:
        # Üç modelin görevleri farklıdır:
        # leke modeli tüm kareyi, yırtık modeli konumu, kontrol modeli doğruluğu inceler.
        self.leke_modeli = YOLO(leke_model_yolu)
        self.yirtik_modeli = YOLO(yirtik_model_yolu)
        self.yirtik_kontrol_modeli = YOLO(yirtik_kontrol_model_yolu)

    @staticmethod
    def _sinif_puani(sonuc, sinif_adi: str) -> float:
        """YOLO sonucundan istediğim sınıfın 0 ile 1 arasındaki puanını alır."""
        sira = next(int(i) for i, ad in sonuc.names.items() if ad == sinif_adi)
        return float(sonuc.probs.data[sira].item())

    def _farkli_boyutlarda_puan(
        self,
        model,
        kare: np.ndarray,
        sinif_adi: str,
        boyutlar: tuple[int, ...],
    ) -> float:
        """Aynı resmi farklı boyutlarda deneyip en yüksek puanı kullanır."""

        # Küçük yırtık bazen büyük görüntü boyutunda daha net bulunabiliyor.
        puanlar = (
            self._sinif_puani(
                model.predict(
                    kare,
                    imgsz=boyut,
                    verbose=False,
                )[0],
                sinif_adi,
            )
            for boyut in boyutlar
        )
        return max(puanlar)

    @staticmethod
    def _yirtik_kutulari(sonuc) -> tuple[YirtikKutusu, ...]:
        """YOLO'nun verdiği koordinatları daha kolay kullanacağım kutulara çevirir."""
        koordinatlar = sonuc.boxes.xyxy.cpu().tolist()
        guvenler = sonuc.boxes.conf.cpu().tolist()
        return tuple(
            YirtikKutusu(
                sol=max(0, int(round(sol))),
                ust=max(0, int(round(ust))),
                sag=max(0, int(round(sag))),
                alt=max(0, int(round(alt))),
                guven=float(guven),
            )
            for (sol, ust, sag, alt), guven in zip(koordinatlar, guvenler)
        )

    @staticmethod
    def _yirtik_var_mi(
        kutular: tuple[YirtikKutusu, ...], kontrol_puani: float
    ) -> bool:
        """Kutu ve kontrol puanlarına bakıp son yırtık kararını verir."""

        # Önce mutlaka bir yırtık kutusu bulunmalı. Sonra iki puandan biri yeterlidir.
        if not kutular:
            return False
        en_iyi_kutu = max(kutu.guven for kutu in kutular)
        return (
            en_iyi_kutu >= YIRTIK_GUCLU_ESIGI
            or kontrol_puani >= YIRTIK_KONTROL_ESIGI
        )

    @staticmethod
    def _leke_var_mi(puan: float, yirtik_var: bool) -> bool:
        """Leke puanını uygun sınırla karşılaştırır."""

        # Yırtık alanı kapatıldığı için birleşik görüntüde daha düşük sınır kullanılıyor.
        esik = BIRLIKTE_LEKE_ESIGI if yirtik_var else LEKE_ESIGI
        return puan >= esik

    def _leke_puani(self, kare: np.ndarray) -> float:
        """Kareyi leke modeline gönderip leke puanını alır."""

        # Kamera görüntüsü dikeyse leke küçük kalabiliyor. Bu yüzden orta kareyi de
        # ayrıca kontrol edip iki sonuçtan yüksek olanı seçiyorum.
        yukseklik, genislik = kare.shape[:2]
        goruntuler = [kare]
        oran = max(yukseklik, genislik) / max(1, min(yukseklik, genislik))
        if yukseklik > genislik and oran >= DIKEY_GORUNTU_ORANI:
            kenar = min(yukseklik, genislik)
            baslangic = (yukseklik - kenar) // 2
            goruntuler.append(kare[baslangic:baslangic + kenar, :])

        sonuclar = self.leke_modeli.predict(
            goruntuler,
            imgsz=LEKE_GORUNTU_BOYUTU,
            verbose=False,
        )
        return max(self._sinif_puani(sonuc, "leke") for sonuc in sonuclar)

    @staticmethod
    def _yirtiklari_kapat(
        kare: np.ndarray,
        kutular: tuple[YirtikKutusu, ...],
    ) -> np.ndarray:
        """Yırtık bölgelerini geçici olarak doldurup leke modelinden gizler."""
        if not kutular:
            return kare
        yukseklik, genislik = kare.shape[:2]
        maske = np.zeros((yukseklik, genislik), dtype=np.uint8)
        for kutu in kutular:
            kutu_genisligi = max(1, kutu.sag - kutu.sol)
            kutu_yuksekligi = max(1, kutu.alt - kutu.ust)
            pay = max(8, round(max(kutu_genisligi, kutu_yuksekligi) * 0.25))
            sol = max(0, kutu.sol - pay)
            ust = max(0, kutu.ust - pay)
            sag = min(genislik - 1, kutu.sag + pay)
            alt = min(yukseklik - 1, kutu.alt + pay)
            cv2.rectangle(maske, (sol, ust), (sag, alt), 255, -1)
        # inpaint, kutunun içini çevresindeki kumaş renklerine benzeterek doldurur.
        return cv2.inpaint(kare, maske, 5, cv2.INPAINT_TELEA)

    @staticmethod
    def _acik_kumasta_leke_puani(kare: np.ndarray) -> float:
        """Modelin kaçırabildiği açık krem kumaştaki silik lekeleri ayrıca arar."""
        yukseklik, genislik = kare.shape[:2]
        olcek = min(1.0, 640.0 / max(yukseklik, genislik))
        if olcek < 1.0:
            goruntu = cv2.resize(
                kare,
                (round(genislik * olcek), round(yukseklik * olcek)),
                interpolation=cv2.INTER_AREA,
            )
        else:
            goruntu = kare

        # LAB renk uzayında parlaklık ve renk farklarını ayrı ayrı ölçmek daha kolaydır.
        lab = cv2.cvtColor(goruntu, cv2.COLOR_BGR2LAB).astype(np.float32)
        orta_alan = lab[
            round(lab.shape[0] * 0.05):round(lab.shape[0] * 0.95),
            round(lab.shape[1] * 0.05):round(lab.shape[1] * 0.95),
        ]
        orta_l, orta_a, orta_b = np.median(orta_alan.reshape(-1, 3), axis=0)
        if orta_l < ACIK_KUMAS_PARLAKLIK_SINIRI:
            return 0.0

        parlaklik_farki = orta_l - lab[:, :, 0]
        renk_farki = np.hypot(lab[:, :, 1] - orta_a, lab[:, :, 2] - orta_b)
        adaylar = (
            (parlaklik_farki >= ACIK_LEKE_PARLAKLIK_FARKI)
            & (renk_farki >= ACIK_LEKE_RENK_FARKI)
        ).astype(np.uint8) * 255

        kenar_y = round(adaylar.shape[0] * 0.04)
        kenar_x = round(adaylar.shape[1] * 0.04)
        adaylar[:kenar_y] = 0
        adaylar[-kenar_y:] = 0
        adaylar[:, :kenar_x] = 0
        adaylar[:, -kenar_x:] = 0
        # Küçük görüntü gürültülerini silip gerçek leke parçalarını birleştiriyorum.
        adaylar = cv2.morphologyEx(
            adaylar, cv2.MORPH_OPEN, np.ones((5, 5), dtype=np.uint8)
        )
        adaylar = cv2.morphologyEx(
            adaylar, cv2.MORPH_CLOSE, np.ones((9, 9), dtype=np.uint8)
        )

        goruntu_alani = adaylar.shape[0] * adaylar.shape[1]
        parca_sayisi, etiketler, bilgiler, _merkezler = cv2.connectedComponentsWithStats(
            adaylar
        )
        # Çok küçük, çok büyük veya uzun çizgi şeklindeki bölgeleri leke saymıyorum.
        for sira in range(1, parca_sayisi):
            _x, _y, parca_genisligi, parca_yuksekligi, alan = bilgiler[sira]
            alan_orani = alan / goruntu_alani
            if not ACIK_LEKE_EN_KUCUK_ALAN <= alan_orani <= ACIK_LEKE_EN_BUYUK_ALAN:
                continue
            oran = max(parca_genisligi, parca_yuksekligi) / max(
                1, min(parca_genisligi, parca_yuksekligi)
            )
            doluluk = alan / max(1, parca_genisligi * parca_yuksekligi)
            if oran <= 4.0 and doluluk >= 0.18:
                guc = float(np.percentile(renk_farki[etiketler == sira], 75))
                return min(0.90, 0.60 + max(0.0, guc - 7.0) * 0.02)
        return 0.0

    def hazirla(self) -> None:
        """Boş bir kare çalıştırıp modelleri canlı testten önce hazır hale getirir."""
        deneme_karesi = np.full((1280, 720, 3), 127, dtype=np.uint8)
        self.kontrol_et(deneme_karesi)

    def kontrol_et(self, kare: np.ndarray) -> GoruntuSonucu:
        """Bir kamera karesini baştan sona kontrol edip sonucu döndürür."""

        # Önce YOLO yırtığın konumunu bulur. İkinci model şüpheli sonucu doğrular.
        yirtik_sonucu = self.yirtik_modeli.predict(
            kare,
            imgsz=YIRTIK_GORUNTU_BOYUTU,
            conf=YIRTIK_ADAY_ESIGI,
            max_det=10,
            verbose=False,
        )[0]
        aday_kutular = self._yirtik_kutulari(yirtik_sonucu)
        yirtik_puani = max((kutu.guven for kutu in aday_kutular), default=0.0)

        # Kutu yoksa yırtık zaten kabul edilmiyor. Kutu çok güçlüyse de YOLO sonucu
        # yeterli oluyor. Yavaş olan ikinci modeli sadece şüpheli kutularda çalıştırıyorum.
        kontrol_puani = 0.0
        kontrol_yapildi = False
        if aday_kutular and yirtik_puani < YIRTIK_GUCLU_ESIGI:
            kontrol_yapildi = True
            kontrol_puani = self._farkli_boyutlarda_puan(
                self.yirtik_kontrol_modeli,
                kare,
                "yirtik",
                YIRTIK_KONTROL_BOYUTLARI,
            )
        yirtik_var = self._yirtik_var_mi(aday_kutular, kontrol_puani)
        yirtik_kutulari = aday_kutular if yirtik_var else ()

        # Yırtık deliği leke sanılmasın diye bu alan leke analizinden önce kapatılır.
        temiz_kare = self._yirtiklari_kapat(kare, yirtik_kutulari)
        model_leke_puani = self._leke_puani(temiz_kare)
        acik_leke_puani = self._acik_kumasta_leke_puani(temiz_kare)
        leke_puani = max(model_leke_puani, acik_leke_puani)
        leke_var = self._leke_var_mi(leke_puani, yirtik_var)

        return GoruntuSonucu(
            leke_puani=leke_puani,
            yirtik_puani=yirtik_puani,
            leke_var=leke_var,
            yirtik_var=yirtik_var,
            yirtik_kutulari=yirtik_kutulari,
            yirtik_kontrol_puani=kontrol_puani,
            yirtik_kontrol_yapildi=kontrol_yapildi,
        )
