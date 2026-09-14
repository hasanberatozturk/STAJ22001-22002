"""Kumaş kusur tespit sistemi için test arayüzü."""

import threading
import time
import tkinter as tk
from collections import deque
from collections.abc import Callable
from tkinter import messagebox

import cv2
import numpy as np
from PIL import Image, ImageTk

try:
    import winsound
except ImportError:  # Raspberry Pi gibi Windows dışındaki sistemlerde bulunmaz.
    winsound = None

from src.config import (
    GEREKEN_OY,
    GORUNTU_GENISLIGI,
    GORUNTU_KONTROL_ARALIGI,
    GORUNTU_YUKSEKLIGI,
    KAMERA_LISTESI,
    KARE_HIZI,
    KARAR_KARE_SAYISI,
    LAZER_FOTOGRAF_KARE_SAYISI,
)
from src.defect_detection import GoruntuSonucu, KusurTespiti
from src.laser_detection import LazerKarsilastirma, lazer_fotograflarini_karsilastir


RENKLER = {
    "arka_plan": "#0b1120",
    "panel": "#131c30",
    "kart": "#1b2942",
    "kart_ikinci": "#172239",
    "kenar": "#2a3a59",
    "goruntu": "#070d1a",
    "pasif": "#27344a",
    "yazi": "#fff9f0",
    "soluk": "#aebbd2",
    "yesil": "#43e6a6",
    "kirmizi": "#ff557f",
    "sari": "#ffd34e",
    "mavi": "#38cfff",
    "mor": "#b99aff",
    "dugme_yesil": "#00a97f",
    "dugme_mavi": "#139bc2",
}


class KumasApp(tk.Tk):
    """Programın kamera, model ve ekrandaki sonuçlarını bir arada yönetir."""

    def __init__(self) -> None:
        super().__init__()
        self.title("Kumaş Kalite Asistanı")
        self.geometry("1280x760")
        self.minsize(1080, 680)
        self.configure(bg=RENKLER["arka_plan"])
        self.protocol("WM_DELETE_WINDOW", self.kapat)

        # Kamerayla ilgili bilgileri burada tutuyorum.
        self.kamera: cv2.VideoCapture | None = None
        self.kamera_bilgisi = ""
        self.bozuk_kare_sayisi = 0
        self.onizleme_acisi: int | None = None
        self.son_kare: np.ndarray | None = None
        self.son_kareler: deque[np.ndarray] = deque(
            maxlen=LAZER_FOTOGRAF_KARE_SAYISI
        )
        self.lazer_kapali_kare: np.ndarray | None = None
        self.lazer_adimi = "kapali"

        # Leke ve yırtık modelleri canlı kamera görüntüsünü kontrol ediyor.
        self.kusur_tespiti: KusurTespiti | None = None
        self.ekrandaki_resim: ImageTk.PhotoImage | None = None

        # Bu değişkenler o anda hangi işlemin açık olduğunu gösteriyor.
        self.kamera_acik = False
        self.analiz_suruyor = False
        self.son_analiz_zamani = 0.0
        self.rgb_bekleme_bitis = 0.0
        self.rgb_test_no = 0
        self.analiz_no = 0

        # Aynı kusur ekranda dururken sesin sürekli tekrar etmesini engelliyorum.
        self.ses_acik = True
        self.son_sesli_kusurlar: set[str] = set()
        self.son_ses_zamani = 0.0

        # Tek bir kareye göre karar vermek yerine son karelerin oyunu tutuyorum.
        self.leke_oylari: deque[bool] = deque(maxlen=KARAR_KARE_SAYISI)
        self.yirtik_oylari: deque[bool] = deque(maxlen=KARAR_KARE_SAYISI)
        self.leke_var = False
        self.yirtik_var = False
        self.kabariklik_var: bool | None = None

        # Kabarıklık kontrolü elle açılır; bu sırada RGB sonucu korunur.
        self.lazer_acik = False
        self._arayuzu_hazirla()
        threading.Thread(target=self._modelleri_yukle, daemon=True).start()

    def _yazi(
        self,
        ust: tk.Misc,
        yazi: str,
        boyut: int = 12,
        renk: str | None = None,
        kalin: bool = False,
    ) -> tk.Label:
        return tk.Label(
            ust,
            text=yazi,
            bg=ust["bg"],
            fg=renk or RENKLER["yazi"],
            font=("Segoe UI", boyut, "bold" if kalin else "normal"),
        )

    def _dugme(
        self,
        ust: tk.Misc,
        yazi: str,
        islem: Callable[[], None],
        renk: str,
        yazi_rengi: str = "white",
    ) -> tk.Button:
        dugme = tk.Button(
            ust,
            text=yazi,
            command=islem,
            bg=renk,
            fg=yazi_rengi,
            relief="flat",
            activebackground=renk,
            activeforeground=yazi_rengi,
            cursor="hand2",
            borderwidth=0,
            highlightthickness=0,
            disabledforeground="#7f8ba1",
            font=("Segoe UI", 10, "bold"),
            padx=10,
            pady=8,
        )
        dugme.normal_renk = renk
        dugme.normal_yazi_rengi = yazi_rengi
        dugme.gecis_no = 0
        dugme.bind("<Enter>", lambda _olay: self._dugmenin_ustune_gelindi(dugme))
        dugme.bind("<Leave>", lambda _olay: self._dugmeden_cikildi(dugme))
        return dugme

    def _dugmenin_ustune_gelindi(self, dugme: tk.Button) -> None:
        if dugme["state"] == "normal":
            self._dugme_rengini_degistir(dugme, self._rengi_ac(dugme.normal_renk))

    def _dugmeden_cikildi(self, dugme: tk.Button) -> None:
        renk = dugme.normal_renk if dugme["state"] == "normal" else RENKLER["pasif"]
        self._dugme_rengini_degistir(dugme, renk)

    def _dugme_durumunu_degistir(
        self,
        dugme: tk.Button,
        kullanilabilir: bool,
    ) -> None:
        """Pasif düğmeleri renkleriyle birlikte anlaşılır hale getirir."""
        if kullanilabilir:
            dugme.config(
                state="normal",
                activebackground=dugme.normal_renk,
                fg=dugme.normal_yazi_rengi,
            )
            hedef_renk = dugme.normal_renk
        else:
            dugme.config(
                state="disabled",
                activebackground=RENKLER["pasif"],
            )
            hedef_renk = RENKLER["pasif"]
        self._dugme_rengini_degistir(dugme, hedef_renk)

    def _dugme_rengini_degistir(self, dugme: tk.Button, hedef_renk: str) -> None:
        """Düğmenin rengini kısa adımlarla değiştirerek geçişi yumuşatır."""
        dugme.gecis_no += 1
        bu_gecis = dugme.gecis_no
        baslangic_rengi = dugme.cget("bg")
        adim_sayisi = 5

        def siradaki_rengi_goster(adim: int) -> None:
            # Fare hızlı hareket ederse eski animasyon yeni rengin üstüne yazmasın.
            if not dugme.winfo_exists() or bu_gecis != dugme.gecis_no:
                return
            oran = adim / adim_sayisi
            yeni_renk = self._renkleri_karistir(
                baslangic_rengi,
                hedef_renk,
                oran,
            )
            dugme.config(bg=yeni_renk)
            if adim < adim_sayisi:
                self.after(12, siradaki_rengi_goster, adim + 1)

        siradaki_rengi_goster(1)

    @staticmethod
    def _renkleri_karistir(baslangic: str, hedef: str, oran: float) -> str:
        """İki onaltılık renk arasında yeni bir renk hesaplar."""
        baslangic_rgb = [int(baslangic[i : i + 2], 16) for i in (1, 3, 5)]
        hedef_rgb = [int(hedef[i : i + 2], 16) for i in (1, 3, 5)]
        yeni_rgb = [
            round(eski + (yeni - eski) * oran)
            for eski, yeni in zip(baslangic_rgb, hedef_rgb)
        ]
        return "#" + "".join(f"{deger:02x}" for deger in yeni_rgb)

    @staticmethod
    def _rengi_ac(renk: str) -> str:
        """Fare düğmenin üstündeyken rengi az miktarda açar."""
        kirmizi, yesil, mavi = (int(renk[i : i + 2], 16) for i in (1, 3, 5))
        return f"#{min(kirmizi + 28, 255):02x}{min(yesil + 28, 255):02x}{min(mavi + 28, 255):02x}"

    def _arayuzu_hazirla(self) -> None:
        """Program açıldığında görünen bütün ekran bölümlerini hazırlar."""

        # Üst bölümde program adı ve o anki çalışma durumu gösteriliyor.
        ust_bolum = tk.Frame(self, bg=RENKLER["panel"], padx=18, pady=10)
        ust_bolum.pack(fill="x")
        baslik_satiri = tk.Frame(ust_bolum, bg=RENKLER["panel"])
        baslik_satiri.pack()
        self._yazi(baslik_satiri, "KUMAŞ KALİTE ASİSTANI", 21, kalin=True).pack(
            side="left"
        )
        self._yazi(
            baslik_satiri,
            "  •  RGB + LAZER",
            9,
            RENKLER["mavi"],
            True,
        ).pack(side="left", padx=(8, 0), pady=(7, 0))
        self.durum_yazisi = self._yazi(ust_bolum, "Modeller yükleniyor…", 10, RENKLER["mavi"])
        self.durum_yazisi.pack(pady=(3, 0))

        # Orta bölümün solunda kamera, sağında kusur sonuçları bulunuyor.
        orta_bolum = tk.Frame(self, bg=RENKLER["arka_plan"], padx=14, pady=12)
        orta_bolum.pack(fill="both", expand=True)

        goruntu_karti = tk.Frame(
            orta_bolum,
            bg=RENKLER["kenar"],
            padx=1,
            pady=1,
        )
        goruntu_karti.pack(side="left", fill="both", expand=True, padx=(0, 16))
        goruntu_basligi = tk.Frame(goruntu_karti, bg=RENKLER["panel"], padx=12, pady=7)
        goruntu_basligi.pack(fill="x")
        self._yazi(goruntu_basligi, "CANLI GÖRÜNTÜ", 10, RENKLER["soluk"], True).pack(
            side="left"
        )
        self.kamera_durum_etiketi = self._yazi(
            goruntu_basligi, "●  KAPALI", 9, RENKLER["soluk"], True
        )
        self.kamera_durum_etiketi.pack(side="right")
        self.dondur_dugmesi = self._dugme(
            goruntu_basligi,
            "↻  OTOMATİK",
            self.onizlemeyi_cevir,
            RENKLER["kart_ikinci"],
            RENKLER["mavi"],
        )
        self.dondur_dugmesi.config(font=("Segoe UI", 8, "bold"), padx=7, pady=2)
        self.dondur_dugmesi.pack(side="right", padx=(0, 12))
        self.ses_dugmesi = self._dugme(
            goruntu_basligi,
            "♪  SES AÇIK",
            self.sesi_degistir,
            RENKLER["kart_ikinci"],
            RENKLER["yesil"],
        )
        self.ses_dugmesi.config(font=("Segoe UI", 8, "bold"), padx=7, pady=2)
        self.ses_dugmesi.pack(side="right", padx=(0, 7))
        self.goruntu_alani = tk.Label(
            goruntu_karti,
            text="Kamera görüntüsü burada gösterilecek",
            bg=RENKLER["goruntu"],
            fg=RENKLER["soluk"],
            font=("Segoe UI", 14, "bold"),
        )
        self.goruntu_alani.pack(fill="both", expand=True)

        yan_bolum = tk.Frame(orta_bolum, bg=RENKLER["arka_plan"], width=370)
        yan_bolum.pack(side="right", fill="y")
        yan_bolum.pack_propagate(False)

        # En önemli bilgi olan birleşik karar sağ bölümün en üstünde gösteriliyor.
        karar_dis = tk.Frame(yan_bolum, bg=RENKLER["kenar"], padx=1, pady=1)
        karar_dis.pack(fill="x", pady=(0, 9))
        karar_kutusu = tk.Frame(
            karar_dis,
            bg=RENKLER["kart_ikinci"],
            padx=14,
            pady=10,
        )
        karar_kutusu.pack(fill="both", expand=True)
        karar_basligi = tk.Frame(karar_kutusu, bg=RENKLER["kart_ikinci"])
        karar_basligi.pack(fill="x")
        self._yazi(karar_basligi, "SONUÇ", 10, RENKLER["soluk"], True).pack(
            side="left"
        )
        self._yazi(karar_basligi, "RGB + LAZER", 8, RENKLER["mavi"], True).pack(
            side="right"
        )
        self.karar_yazisi = self._yazi(
            karar_kutusu, "BEKLİYOR", 21, RENKLER["sari"], True
        )
        self.karar_yazisi.config(anchor="w", justify="left", wraplength=330)
        self.karar_yazisi.pack(anchor="w", pady=(4, 2))
        self._yazi(
            karar_kutusu,
            "Üç kontrolün ortak sonucu",
            8,
            RENKLER["soluk"],
        ).pack(anchor="w")
        self.karar_vurgusu = tk.Frame(karar_kutusu, bg=RENKLER["sari"], height=3)
        self.karar_vurgusu.pack(fill="x", pady=(8, 0))

        self._yazi(yan_bolum, "KUSUR DURUMU", 9, RENKLER["soluk"], True).pack(
            anchor="w", pady=(0, 5)
        )

        # Her kusur tek satırda gösterildiği için sonuçlar daha hızlı okunabiliyor.
        self.kartlar: dict[str, tuple[tk.Label, tk.Label]] = {}
        self.kart_vurgulari: dict[str, tk.Frame] = {}
        self.kart_simgeleri: dict[str, tk.Label] = {}
        kart_bilgileri = (
            ("leke", "●", "LEKE"),
            ("yirtik", "●", "YIRTIK"),
            ("kabariklik", "●", "KABARIKLIK"),
        )
        for anahtar, simge, baslik in kart_bilgileri:
            kart = tk.Frame(yan_bolum, bg=RENKLER["kenar"], padx=1, pady=1)
            kart.pack(fill="x", pady=(0, 6))
            kart_ici = tk.Frame(kart, bg=RENKLER["kart"])
            kart_ici.pack(fill="both", expand=True)
            vurgu = tk.Frame(kart_ici, bg=RENKLER["sari"], width=4)
            vurgu.pack(side="left", fill="y")
            vurgu.pack_propagate(False)
            icerik = tk.Frame(kart_ici, bg=RENKLER["kart"], padx=11, pady=7)
            icerik.pack(side="left", fill="both", expand=True)
            ust_satir = tk.Frame(icerik, bg=RENKLER["kart"])
            ust_satir.pack(fill="x")
            simge_yazisi = self._yazi(
                ust_satir, simge, 9, RENKLER["sari"], True
            )
            simge_yazisi.pack(side="left")
            self._yazi(ust_satir, baslik, 10, RENKLER["soluk"], True).pack(
                side="left", padx=(6, 0)
            )
            sonuc_yazisi = self._yazi(ust_satir, "BEKLİYOR", 13, RENKLER["sari"], True)
            sonuc_yazisi.config(anchor="e", justify="right", wraplength=185)
            sonuc_yazisi.pack(side="right")
            aciklama = self._yazi(icerik, "Henüz ölçülmedi", 8, RENKLER["soluk"])
            aciklama.config(anchor="w", justify="left", wraplength=320)
            aciklama.pack(fill="x", pady=(3, 0))
            self.kartlar[anahtar] = (sonuc_yazisi, aciklama)
            self.kart_vurgulari[anahtar] = vurgu
            self.kart_simgeleri[anahtar] = simge_yazisi

        self._yazi(yan_bolum, "KABARIKLIK ÖLÇÜMÜ", 9, RENKLER["soluk"], True).pack(
            anchor="w", pady=(3, 5)
        )
        adim_karti = tk.Frame(yan_bolum, bg=RENKLER["kart_ikinci"], padx=10, pady=8)
        adim_karti.pack(fill="x", pady=(0, 8))
        self.lazer_adim_etiketleri: list[tk.Label] = []
        for sira, ad in enumerate(("RGB", "KAPALI", "AÇIK", "SONUÇ"), start=1):
            adim = self._yazi(adim_karti, f"{sira}  {ad}", 8, RENKLER["soluk"], True)
            adim.pack(side="left", expand=True)
            self.lazer_adim_etiketleri.append(adim)

        self.baslat_dugmesi = self._dugme(
            yan_bolum, "CANLI TESTİ BAŞLAT", self.baslat, RENKLER["dugme_yesil"]
        )
        self.baslat_dugmesi.pack(fill="x", pady=(0, 5))
        self.lazer_dugmesi = self._dugme(
            yan_bolum,
            "LAZER KAPALI FOTOĞRAFI AL",
            self.lazer_adimini_ilerlet,
            RENKLER["dugme_mavi"],
        )
        self.lazer_dugmesi.pack(fill="x", pady=(0, 5))
        self.durdur_dugmesi = self._dugme(
            yan_bolum,
            "KAMERAYI DURDUR",
            self.durdur,
            RENKLER["kart_ikinci"],
            RENKLER["kirmizi"],
        )
        self.durdur_dugmesi.config(
            highlightthickness=1,
            highlightbackground=RENKLER["kirmizi"],
            highlightcolor=RENKLER["kirmizi"],
        )
        self.durdur_dugmesi.pack(fill="x")
        self._dugme_durumunu_degistir(self.baslat_dugmesi, False)
        self._dugmeleri_ayarla(False)
        self._lazer_adimini_goster()

    def _dugmeleri_ayarla(self, kullanilabilir: bool) -> None:
        self._dugme_durumunu_degistir(self.durdur_dugmesi, kullanilabilir)
        self._dugme_durumunu_degistir(self.lazer_dugmesi, kullanilabilir)

    def _lazer_adimini_goster(self) -> None:
        """Kullanıcının lazer ölçümünde hangi adımda olduğunu renkle gösterir."""
        if not self.kamera_acik:
            renkler = [RENKLER["soluk"]] * 4
        elif self.lazer_adimi == "kapali":
            renkler = [
                RENKLER["mavi"],
                RENKLER["soluk"],
                RENKLER["soluk"],
                RENKLER["soluk"],
            ]
        elif self.lazer_adimi == "acik":
            renkler = [
                RENKLER["yesil"],
                RENKLER["yesil"],
                RENKLER["mavi"],
                RENKLER["soluk"],
            ]
        elif self.lazer_adimi == "hesaplaniyor":
            renkler = [
                RENKLER["yesil"],
                RENKLER["yesil"],
                RENKLER["yesil"],
                RENKLER["mavi"],
            ]
        else:
            renkler = [RENKLER["yesil"]] * 4

        for etiket, renk in zip(self.lazer_adim_etiketleri, renkler):
            etiket.config(fg=renk)

    def onizlemeyi_cevir(self) -> None:
        """Canlı görüntüyü saat yönünde 90 derece çevirir."""
        mevcut_aci = self.onizleme_acisi or 0
        self.onizleme_acisi = (mevcut_aci + 90) % 360
        self.dondur_dugmesi.config(text=f"↻  {self.onizleme_acisi}°")

    def sesi_degistir(self) -> None:
        """Kusur bulunduğunda çalan uyarı sesini açıp kapatır."""
        self.ses_acik = not self.ses_acik
        if self.ses_acik:
            yazi = "♪  SES AÇIK"
            renk = RENKLER["yesil"]
            # Ses yeniden açıldığında ekrandaki yeni kararı tekrar değerlendirebilir.
            self.son_sesli_kusurlar.clear()
        else:
            yazi = "♪  SES KAPALI"
            renk = RENKLER["soluk"]

        self.ses_dugmesi.normal_yazi_rengi = renk
        self.ses_dugmesi.config(text=yazi, fg=renk, activeforeground=renk)

    def _kusur_sesini_kontrol_et(self, kusurlar: list[str]) -> None:
        """Karara yeni bir kusur eklendiyse bir kez uyarı sesi çalar."""
        mevcut_kusurlar = set(kusurlar)
        if not mevcut_kusurlar:
            self.son_sesli_kusurlar.clear()
            return

        yeni_kusurlar = mevcut_kusurlar - self.son_sesli_kusurlar
        if not self.ses_acik:
            self.son_sesli_kusurlar = mevcut_kusurlar
            return
        if not yeni_kusurlar:
            self.son_sesli_kusurlar = mevcut_kusurlar
            return

        simdi = time.monotonic()
        if simdi - self.son_ses_zamani < 1.0:
            # Bir saniyelik aralık dolunca aynı yeni kusur tekrar kontrol edilir.
            return

        self.son_sesli_kusurlar = mevcut_kusurlar
        self.son_ses_zamani = simdi
        threading.Thread(target=self._uyari_sesi_cal, daemon=True).start()

    def _uyari_sesi_cal(self) -> None:
        """Arayüzü bekletmeden kısa ve fark edilir iki ton çalar."""
        if winsound is not None:
            try:
                winsound.Beep(880, 110)
                winsound.Beep(1175, 150)
                return
            except (RuntimeError, OSError):
                pass
        try:
            self.after(0, self.bell)
        except tk.TclError:
            # Program kapanırken bekleyen ses işi kalırsa hata göstermesine gerek yok.
            pass

    def _onizleme_icin_cevir(self, kare: np.ndarray) -> np.ndarray:
        """Model karesini değiştirmeden yalnızca ekrandaki görüntüyü döndürür."""
        if self.onizleme_acisi is None:
            yukseklik, genislik = kare.shape[:2]
            self.onizleme_acisi = 90 if yukseklik > genislik else 0
            self.dondur_dugmesi.config(text=f"↻  {self.onizleme_acisi}°")

        if self.onizleme_acisi == 90:
            return cv2.rotate(kare, cv2.ROTATE_90_CLOCKWISE)
        if self.onizleme_acisi == 180:
            return cv2.rotate(kare, cv2.ROTATE_180)
        if self.onizleme_acisi == 270:
            return cv2.rotate(kare, cv2.ROTATE_90_COUNTERCLOCKWISE)
        return kare

    def _durum_yaz(self, yazi: str, renk: str) -> None:
        self.durum_yazisi.config(text=yazi, fg=renk)

    def _goruntu_sonucunu_sifirla(self) -> None:
        """Yeni test başlarken eski leke ve yırtık kararlarını temizler."""
        self.leke_oylari.clear()
        self.yirtik_oylari.clear()
        self.son_sesli_kusurlar.clear()
        self.leke_var = False
        self.yirtik_var = False

    def _karti_beklemeye_al(
        self,
        anahtar: str,
        sonuc: str,
        aciklama: str,
        renk: str | None = None,
    ) -> None:
        """Henüz tamamlanmayan bir kontrolün kartını tek yerden günceller."""
        kart_rengi = renk or RENKLER["sari"]
        sonuc_yazisi, alt_yazi = self.kartlar[anahtar]
        sonuc_yazisi.config(text=sonuc, fg=kart_rengi)
        alt_yazi.config(text=aciklama)
        self.kart_vurgulari[anahtar].config(bg=kart_rengi)
        self.kart_simgeleri[anahtar].config(fg=kart_rengi)

    def _modelleri_yukle(self) -> None:
        """Modeller yüklenirken program ekranının donmasını engeller."""

        # Model yükleme uzun sürebildiği için bu fonksiyon ayrı iş parçacığında çalışıyor.
        try:
            self.kusur_tespiti = KusurTespiti()
            self.kusur_tespiti.hazirla()
            self.after(0, self._modeller_hazir)
        except Exception as hata:
            self.after(
                0,
                self._durum_yaz,
                f"Model yükleme hatası: {hata}",
                RENKLER["kirmizi"],
            )

    def _modeller_hazir(self) -> None:
        """Model yüklemesi bitince başlat düğmesini kullanıma açar."""
        self._durum_yaz(
            "Modeller hazır • Canlı testi başlatabilirsiniz",
            RENKLER["yesil"],
        )
        self._dugme_durumunu_degistir(self.baslat_dugmesi, True)

    @staticmethod
    def _kare_gecerli_mi(kare: np.ndarray | None) -> bool:
        """Kameradan gerçekten kullanılabilir bir görüntü gelip gelmediğine bakar."""

        # Bazı sanal kameralar bağlı değilken boş, siyah veya yeşil kare verebiliyor.
        if kare is None or kare.size == 0:
            return False
        renk_degisimi = float(
            np.mean(np.std(kare.astype(np.float32), axis=(0, 1)))
        )
        return renk_degisimi >= 0.5

    @classmethod
    def _kamerayi_ac(cls) -> tuple[cv2.VideoCapture | None, str | None]:
        """Kamera listesini sırayla dener ve görüntü veren ilk kamerayı seçer."""
        sistemler = {"MSMF": cv2.CAP_MSMF, "DSHOW": cv2.CAP_DSHOW}
        for numara, sistem_adi in KAMERA_LISTESI:
            kamera = cv2.VideoCapture(numara, sistemler[sistem_adi])
            if not kamera.isOpened():
                kamera.release()
                continue
            kamera.set(cv2.CAP_PROP_FRAME_WIDTH, GORUNTU_GENISLIGI)
            kamera.set(cv2.CAP_PROP_FRAME_HEIGHT, GORUNTU_YUKSEKLIGI)
            kamera.set(cv2.CAP_PROP_FPS, KARE_HIZI)
            # Destekleyen kameralarda eski karelerin birikmesini azaltır.
            kamera.set(cv2.CAP_PROP_BUFFERSIZE, 1)

            # Kameranın açılması yetmez; birkaç gerçek kare okuyabildiğini de kontrol ediyorum.
            kare = None
            for _ in range(6):
                okundu, aday_kare = kamera.read()
                if okundu and aday_kare is not None:
                    # Bağlantısız sanal kameraların siyah/yeşil tek renk karesini ele.
                    if cls._kare_gecerli_mi(aday_kare):
                        kare = aday_kare
                        break
            if kare is not None:
                yukseklik, genislik = kare.shape[:2]
                return kamera, f"{sistem_adi}/{numara} • {genislik}x{yukseklik}"
            kamera.release()
        return None, None

    def baslat(self) -> None:
        """Başlat düğmesine basılınca kamerayı ve canlı testi çalıştırır."""
        if self.kusur_tespiti is None:
            messagebox.showwarning("Bekleyin", "Modeller henüz hazır değil.")
            return
        if self.kamera_acik:
            return
        kamera, kamera_bilgisi = self._kamerayi_ac()
        if kamera is None or kamera_bilgisi is None:
            messagebox.showerror(
                "Kamera açılamadı",
                "Geçerli kamera görüntüsü bulunamadı. Kamera bağlantısını kontrol "
                "edip yeniden deneyin.",
            )
            return
        self.kamera = kamera
        self.kamera_bilgisi = kamera_bilgisi
        self.son_kare = None
        self.son_kareler.clear()
        self.lazer_kapali_kare = None
        self.lazer_adimi = "kapali"
        self.lazer_acik = False
        self.rgb_bekleme_bitis = 0.0
        self.rgb_test_no += 1
        self.analiz_no += 1
        self.analiz_suruyor = False
        self._goruntu_sonucunu_sifirla()
        self.kabariklik_var = None
        self.kamera_acik = True
        self._dugme_durumunu_degistir(self.baslat_dugmesi, False)
        self._dugmeleri_ayarla(True)
        self._lazer_adimini_goster()
        self.kamera_durum_etiketi.config(text="●  CANLI", fg=RENKLER["yesil"])
        self._karti_beklemeye_al(
            "leke", "BEKLİYOR", "İlk model sonucu bekleniyor"
        )
        self._karti_beklemeye_al(
            "yirtik", "BEKLİYOR", "İlk model sonucu bekleniyor"
        )
        self._karti_beklemeye_al(
            "kabariklik", "BEKLİYOR", "İki fotoğraf henüz alınmadı"
        )
        self.karar_yazisi.config(text="BEKLİYOR", fg=RENKLER["sari"])
        self.karar_vurgusu.config(bg=RENKLER["sari"])
        self._durum_yaz(
            f"Kamera açık: {kamera_bilgisi} • Lazer kapalı • RGB analizi çalışıyor",
            RENKLER["yesil"],
        )
        self._kamerayi_guncelle()

    def lazer_adimini_ilerlet(self) -> None:
        """Lazer kapalı-açık fotoğraf alma adımlarını tek düğmeyle yönetir."""
        if not self.kamera_acik or self.son_kare is None:
            return

        if self.lazer_adimi == "kapali":
            # İlk fotoğraf lazer kapalıyken alınır. Bundan sonra RGB sonucu korunur.
            self.lazer_kapali_kare = self._kararli_kareyi_al()
            self.lazer_adimi = "acik"
            self.lazer_acik = True
            # Lazer moduna geçmeden önce başlamış RGB sonucu daha sonra ekrana gelmesin.
            self.rgb_test_no += 1
            self.analiz_no += 1
            self.analiz_suruyor = False
            self.kabariklik_var = None
            self.lazer_dugmesi.config(text="LAZER AÇIK FOTOĞRAFI AL")
            self._karti_beklemeye_al(
                "kabariklik",
                "İKİNCİ FOTOĞRAF",
                "Lazeri açın, 1 saniye bekleyip düğmeye tekrar basın",
            )
            self._durum_yaz(
                "Lazer kapalı fotoğraf alındı • Kumaşı oynatmadan lazeri açın",
                RENKLER["mor"],
            )

        elif self.lazer_adimi == "acik":
            # İkinci fotoğrafı arka planda karşılaştırırken arayüz donmaz.
            lazer_acik_kare = self._kararli_kareyi_al()
            self.lazer_adimi = "hesaplaniyor"
            self.lazer_dugmesi.config(text="KARŞILAŞTIRILIYOR…")
            self._dugme_durumunu_degistir(self.lazer_dugmesi, False)
            self._karti_beklemeye_al(
                "kabariklik", "HESAPLANIYOR", "İki fotoğraf karşılaştırılıyor"
            )
            threading.Thread(
                target=self._lazer_fotograflarini_isle,
                args=(self.lazer_kapali_kare.copy(), lazer_acik_kare),
                daemon=True,
            ).start()

        elif self.lazer_adimi == "tamam":
            # Kullanıcı lazeri kapattıktan sonra RGB analizi yeniden başlar.
            self.lazer_adimi = "kapali"
            self.lazer_acik = False
            self.lazer_kapali_kare = None
            # Lazer sonucu, ölçüm tamamlandığında birleşik kararda gösterilir. RGB'ye
            # dönmek yeni bir kontrol başladığı anlamına geldiği için eski sonuç silinir.
            self.kabariklik_var = None
            self._karti_beklemeye_al(
                "kabariklik",
                "BEKLİYOR",
                "Yeni lazer ölçümü henüz yapılmadı",
            )
            self.son_kareler.clear()
            # Parlak lazer kapatılınca telefon kamerasının pozlaması hemen düzelmeyebilir.
            # Bir saniye bekleyip RGB analizini yeni bir oturum olarak başlatıyorum.
            self.rgb_bekleme_bitis = time.monotonic() + 1.0
            self.rgb_test_no += 1
            self.analiz_no += 1
            self.analiz_suruyor = False
            self.son_analiz_zamani = 0.0
            self.lazer_dugmesi.config(text="LAZER KAPALI FOTOĞRAFI AL")
            self.leke_oylari.clear()
            self.yirtik_oylari.clear()
            self._durum_yaz(
                f"Kamera açık: {self.kamera_bilgisi} • RGB analizi yeniden hazırlanıyor",
                RENKLER["yesil"],
            )
            self.after(1050, self._rgb_hazir_mesaji, self.rgb_test_no)
        self._lazer_adimini_goster()
        self._karari_guncelle()

    def _kararli_kareyi_al(self) -> np.ndarray:
        """Son üç kamera karesini birleştirip daha temiz bir fotoğraf oluşturur."""
        if not self.son_kareler:
            return self.son_kare.copy()
        if len(self.son_kareler) == 1:
            return self.son_kareler[0].copy()
        kareler = np.stack(tuple(self.son_kareler), axis=0)
        return np.median(kareler, axis=0).astype(np.uint8)

    def _rgb_hazir_mesaji(self, test_no: int) -> None:
        """Lazer sonrasında kamera toparlanınca RGB'nin çalıştığını bildirir."""
        if (
            self.kamera_acik
            and not self.lazer_acik
            and test_no == self.rgb_test_no
        ):
            self._durum_yaz(
                f"Kamera açık: {self.kamera_bilgisi} • RGB analizi çalışıyor",
                RENKLER["yesil"],
            )

    def _lazer_fotograflarini_isle(
        self,
        lazer_kapali_kare: np.ndarray,
        lazer_acik_kare: np.ndarray,
    ) -> None:
        """İki fotoğrafı arka planda karşılaştırır."""
        try:
            sonuc = lazer_fotograflarini_karsilastir(
                lazer_kapali_kare,
                lazer_acik_kare,
            )
            self.after(0, lambda deger=sonuc: self._lazer_sonucunu_goster(deger))
        except Exception as hata:
            self.after(0, lambda mesaj=str(hata): self._lazer_hatasini_goster(mesaj))

    def _lazer_sonucunu_goster(self, sonuc: LazerKarsilastirma) -> None:
        """İki fotoğraftan bulunan kabarıklık sonucunu ekrana yazar."""
        if not self.kamera_acik or self.lazer_adimi != "hesaplaniyor":
            return
        self.lazer_adimi = "tamam"
        self.kabariklik_var = sonuc.kabariklik_var
        self.lazer_dugmesi.config(text="LAZERİ KAPAT • RGB TESTİNE DÖN")
        self._dugme_durumunu_degistir(self.lazer_dugmesi, True)
        self._lazer_adimini_goster()
        self._kart_guncelle(
            "kabariklik",
            sonuc.kabariklik_var,
            f"{sonuc.yon.title()} lazer • Sapma {sonuc.sapma:.2f} / {sonuc.esik:.2f} px",
        )
        self._durum_yaz(
            "Lazer sonucu hazır • Lazeri kapatıp RGB testine dönün",
            RENKLER["yesil"],
        )
        self._karari_guncelle()

    def _lazer_hatasini_goster(self, mesaj: str) -> None:
        """Fotoğraflar uygun değilse lazer açık fotoğrafın yeniden alınmasını ister."""
        if not self.kamera_acik:
            return
        self.lazer_adimi = "acik"
        self.lazer_dugmesi.config(text="LAZER AÇIK FOTOĞRAFI TEKRAR AL")
        self._dugme_durumunu_degistir(self.lazer_dugmesi, True)
        self._lazer_adimini_goster()
        self._karti_beklemeye_al("kabariklik", "TEKRAR DENE", mesaj)
        self._durum_yaz(
            "Lazer çizgisi okunamadı • Kumaşı oynatmadan açık fotoğrafı tekrar alın",
            RENKLER["sari"],
        )

    def durdur(self) -> None:
        """Kamerayı güvenli şekilde kapatır ve eski sonuçları temizler."""
        self.kamera_acik = False
        self.lazer_acik = False
        self.lazer_adimi = "kapali"
        self.rgb_test_no += 1
        self.analiz_no += 1
        self.analiz_suruyor = False
        self.rgb_bekleme_bitis = 0.0
        self.son_kare = None
        self.son_kareler.clear()
        self.lazer_kapali_kare = None
        self._goruntu_sonucunu_sifirla()
        self.kabariklik_var = None
        if self.kamera is not None:
            self.kamera.release()
        self.kamera = None
        self._dugme_durumunu_degistir(self.baslat_dugmesi, True)
        self.lazer_dugmesi.config(text="LAZER KAPALI FOTOĞRAFI AL")
        self._dugmeleri_ayarla(False)
        self._lazer_adimini_goster()
        self.kamera_durum_etiketi.config(text="●  KAPALI", fg=RENKLER["soluk"])
        for anahtar in self.kartlar:
            self._karti_beklemeye_al(
                anahtar,
                "BEKLİYOR",
                "Kamera kapalı",
                RENKLER["soluk"],
            )
        self.karar_yazisi.config(text="DURDURULDU", fg=RENKLER["soluk"])
        self.karar_vurgusu.config(bg=RENKLER["soluk"])
        self.ekrandaki_resim = None
        self.goruntu_alani.config(
            image="",
            text="Kamera görüntüsü burada gösterilecek",
        )
        self._durum_yaz("Kamera durduruldu", RENKLER["sari"])

    def _kamerayi_guncelle(self) -> None:
        """Kameradan sürekli kare alır, ekrana verir ve analizleri sıraya koyar."""
        if not self.kamera_acik or self.kamera is None:
            return
        okundu, kare = self.kamera.read()
        if not okundu:
            self._durum_yaz("Kameradan kare alınamadı", RENKLER["kirmizi"])
            self.after(100, self._kamerayi_guncelle)
            return
        if not self._kare_gecerli_mi(kare):
            self.bozuk_kare_sayisi += 1
            if self.bozuk_kare_sayisi >= 10:
                self._durum_yaz(
                    "Kamera geçici olarak tek renk görüntü veriyor • Bağlantı kontrol ediliyor",
                    RENKLER["kirmizi"],
                )
            self.after(100, self._kamerayi_guncelle)
            return
        kamera_duzeldi = self.bozuk_kare_sayisi > 0
        self.bozuk_kare_sayisi = 0
        self.son_kare = kare.copy()
        self.son_kareler.append(kare.copy())
        if kamera_duzeldi:
            self._durum_yaz(
                f"Kamera açık: {self.kamera_bilgisi} • Lazer kapalıyken RGB analizi çalışır",
                RENKLER["yesil"],
            )
        # Dikey kamera görüntüsü yalnızca önizlemede çevrilir. Modeller kameradan gelen
        # asıl kareyi kullanmaya devam ettiği için bu seçenek sonuçları değiştirmez.
        simdi = time.monotonic()
        onizleme_karesi = self._onizleme_icin_cevir(kare)
        renkli_kare = cv2.cvtColor(onizleme_karesi, cv2.COLOR_BGR2RGB)
        resim = Image.fromarray(renkli_kare)
        # Görüntüyü sabit bir boyuta değil, pencerenin o anki boş alanına sığdırıyorum.
        alan_genisligi = max(self.goruntu_alani.winfo_width() - 16, 320)
        alan_yuksekligi = max(self.goruntu_alani.winfo_height() - 16, 240)
        resim.thumbnail(
            (alan_genisligi, alan_yuksekligi),
            Image.Resampling.BILINEAR,
        )
        self.ekrandaki_resim = ImageTk.PhotoImage(resim)
        self.goruntu_alani.config(image=self.ekrandaki_resim, text="")
        # Manuel kabarıklık kontrolünde yalnızca kamera görüntüsü gösterilir.
        # RGB modelleri durur ve önceki leke-yırtık sonuçları değiştirilmez.
        if (
            not self.lazer_acik
            and not self.analiz_suruyor
            and simdi >= self.rgb_bekleme_bitis
            and simdi - self.son_analiz_zamani >= GORUNTU_KONTROL_ARALIGI
        ):
            self.son_analiz_zamani = simdi
            self.analiz_suruyor = True
            self.analiz_no += 1
            analiz_no = self.analiz_no
            test_no = self.rgb_test_no
            threading.Thread(
                target=self._kusurlari_kontrol_et,
                args=(kare.copy(), test_no, analiz_no),
                daemon=True,
            ).start()
        self.after(30, self._kamerayi_guncelle)

    def _kusurlari_kontrol_et(
        self,
        kare: np.ndarray,
        test_no: int,
        analiz_no: int,
    ) -> None:
        """Seçilen kamera karesini leke ve yırtık modellerine gönderir."""

        # Model hesabı ayrı iş parçacığında çalıştığı için arayüz kullanılabilir kalıyor.
        try:
            if self.kusur_tespiti is not None:
                sonuc = self.kusur_tespiti.kontrol_et(kare)
                self.after(
                    0,
                    lambda s=sonuc, no=test_no: self._kusur_sonucunu_goster(s, no),
                )
        except Exception as hata:
            self.after(
                0,
                self._goruntu_hatasini_goster,
                f"Görüntü kontrol hatası: {hata}",
                test_no,
            )
        finally:
            self.after(0, self._analiz_bitti, analiz_no)

    def _analiz_bitti(self, analiz_no: int) -> None:
        """Son analiz bittiyse yeni bir kareye izin verir."""
        if analiz_no == self.analiz_no:
            self.analiz_suruyor = False

    def _goruntu_hatasini_goster(self, mesaj: str, test_no: int) -> None:
        """Önceki testten kalan bir hatayı ekranda göstermez."""
        if test_no == self.rgb_test_no:
            self._durum_yaz(mesaj, RENKLER["kirmizi"])

    def _kusur_sonucunu_goster(
        self,
        sonuc: GoruntuSonucu,
        test_no: int,
    ) -> None:
        """Model sonucunu oylamaya ekler ve ekrandaki kartlara yazar."""
        if (
            not self.kamera_acik
            or self.lazer_acik
            or test_no != self.rgb_test_no
        ):
            return
        # Bir kusurun tek karede yanlış çıkması sonucu hemen değiştirmesin diye
        # son birkaç kareden çoğunluk oyu alıyorum.
        self.leke_oylari.append(sonuc.leke_var)
        self.yirtik_oylari.append(sonuc.yirtik_var)
        leke_var = sum(self.leke_oylari) >= min(
            GEREKEN_OY, len(self.leke_oylari)
        )
        yirtik_var = sum(self.yirtik_oylari) >= min(
            GEREKEN_OY, len(self.yirtik_oylari)
        )
        self.leke_var = leke_var
        self.yirtik_var = yirtik_var
        leke_aciklamasi = (
            f"Güven %{sonuc.leke_puani * 100:.0f} • "
            f"Oy {sum(self.leke_oylari)}/{len(self.leke_oylari)}"
        )
        kontrol_yazisi = (
            f"Kontrol %{sonuc.yirtik_kontrol_puani * 100:.0f}"
            if sonuc.yirtik_kontrol_yapildi
            else "Ek kontrol gerekmedi"
        )
        self._kart_guncelle("leke", leke_var, leke_aciklamasi)
        self._kart_guncelle(
            "yirtik",
            yirtik_var,
            f"Kutu %{sonuc.yirtik_puani * 100:.0f} • "
            f"{kontrol_yazisi} • "
            f"Oy {sum(self.yirtik_oylari)}/{len(self.yirtik_oylari)}",
        )
        self._karari_guncelle()

    def _kart_guncelle(self, anahtar: str, kusur_var: bool, aciklama: str) -> None:
        sonuc_yazisi, alt_yazi = self.kartlar[anahtar]
        sonuc_rengi = RENKLER["kirmizi"] if kusur_var else RENKLER["yesil"]
        sonuc_yazisi.config(
            text="VAR" if kusur_var else "YOK",
            fg=sonuc_rengi,
        )
        alt_yazi.config(text=aciklama)
        self.kart_vurgulari[anahtar].config(bg=sonuc_rengi)
        self.kart_simgeleri[anahtar].config(fg=sonuc_rengi)

    def _karari_guncelle(self) -> None:
        """Bulunan kusurları ekrandaki birleşik karar bölümünde gösterir."""
        kusurlar = [
            ad
            for ad, var_mi in (
                ("LEKE", self.leke_var),
                ("YIRTIK", self.yirtik_var),
                ("KABARIKLIK", self.kabariklik_var),
            )
            if var_mi
        ]
        self._kusur_sesini_kontrol_et(kusurlar)
        if kusurlar:
            karar = " + ".join(kusurlar)
            karar_rengi = RENKLER["kirmizi"]
        elif self.lazer_acik and self.kabariklik_var is None:
            karar = "LAZER TESTİ"
            karar_rengi = RENKLER["sari"]
        elif self.kabariklik_var is None:
            karar = "RGB NORMAL"
            karar_rengi = RENKLER["mavi"]
        else:
            karar = "NORMAL"
            karar_rengi = RENKLER["yesil"]
        self.karar_yazisi.config(text=karar, fg=karar_rengi)
        self.karar_vurgusu.config(bg=karar_rengi)

    def kapat(self) -> None:
        self.durdur()
        self.destroy()


if __name__ == "__main__":
    KumasApp().mainloop()
