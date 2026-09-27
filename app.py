"""Kumaş kusur tespit sistemi için test arayüzü."""

import threading
import time
import tkinter as tk
from collections import deque
from tkinter import messagebox

import cv2
import numpy as np
from PIL import ImageTk

try:
    import winsound
except ImportError:  # Raspberry Pi gibi Windows dışındaki sistemlerde bulunmaz.
    winsound = None

from src.config import (
    REQUIRED_VOTES,
    ANALYSIS_INTERVAL,
    VOTE_FRAME_COUNT,
    LASER_PHOTO_FRAME_COUNT,
)
from src.camera import kamera_ac, kare_gecerli_mi
from src.ui import KumasArayuzu, COLORS
from src.defect_detection import GoruntuSonucu, KusurTespiti
from src.laser_detection import LazerKarsilastirma, lazer_fotograflarini_karsilastir


class KumasApp(KumasArayuzu):
    """Kamera akışını, analiz işlerini ve RGB/lazer adımlarını yönetir."""

    def __init__(self) -> None:
        super().__init__()
        self.title("Kumaş Kalite Asistanı")
        self.geometry("1280x760")
        self.minsize(1080, 680)
        self.configure(bg=COLORS["arka_plan"])
        self.protocol("WM_DELETE_WINDOW", self.kapat)

        # Kamerayla ilgili bilgileri burada tutuyorum.
        self.camera: cv2.VideoCapture | None = None
        self.camera_info = ""
        self.bad_frame_count = 0
        self.preview_angle: int | None = None
        self.last_frame: np.ndarray | None = None
        self.recent_frames: deque[np.ndarray] = deque(
            maxlen=LASER_PHOTO_FRAME_COUNT
        )
        self.laser_off_frame: np.ndarray | None = None
        self.laser_step = "kapali"

        # Leke ve yırtık modelleri canlı kamera görüntüsünü kontrol ediyor.
        self.detector: KusurTespiti | None = None
        self.display_image: ImageTk.PhotoImage | None = None

        # Bu değişkenler o anda hangi işlemin açık olduğunu gösteriyor.
        self.camera_running = False
        self.analysis_running = False
        self.last_analysis_time = 0.0
        self.rgb_ready_time = 0.0
        self.rgb_test_id = 0
        self.analysis_id = 0

        # Aynı kusur ekranda dururken sesin sürekli tekrar etmesini engelliyorum.
        self.sound_enabled = True
        self.last_alert_defects: set[str] = set()
        self.last_alert_time = 0.0

        # Tek bir kareye göre karar vermek yerine son karelerin oyunu tutuyorum.
        self.stain_votes: deque[bool] = deque(maxlen=VOTE_FRAME_COUNT)
        self.tear_votes: deque[bool] = deque(maxlen=VOTE_FRAME_COUNT)
        self.has_stain = False
        self.has_tear = False
        self.has_bump: bool | None = None

        # Kabarıklık kontrolü elle açılır; bu sırada RGB sonucu korunur.
        self.laser_active = False
        self._arayuzu_hazirla()
        threading.Thread(target=self._modelleri_yukle, daemon=True).start()

    def sesi_degistir(self) -> None:
        """Kusur bulunduğunda çalan uyarı sesini açıp kapatır."""
        self.sound_enabled = not self.sound_enabled
        if self.sound_enabled:
            text = "♪  SES AÇIK"
            color = COLORS["yesil"]
            # Ses yeniden açıldığında ekrandaki yeni kararı tekrar değerlendirebilir.
            self.last_alert_defects.clear()
        else:
            text = "♪  SES KAPALI"
            color = COLORS["soluk"]

        self.sound_button.base_text_color = color
        self.sound_button.config(text=text, fg=color, activeforeground=color)

    def _kusur_sesini_kontrol_et(self, defects: list[str]) -> None:
        """Karara yeni bir kusur eklendiyse bir kez uyarı sesi çalar."""
        current_defects = set(defects)
        if not current_defects:
            self.last_alert_defects.clear()
            return

        new_defects = current_defects - self.last_alert_defects
        if not self.sound_enabled:
            self.last_alert_defects = current_defects
            return
        if not new_defects:
            self.last_alert_defects = current_defects
            return

        now = time.monotonic()
        if now - self.last_alert_time < 1.0:
            # Bir saniyelik aralık dolunca aynı yeni kusur tekrar kontrol edilir.
            return

        self.last_alert_defects = current_defects
        self.last_alert_time = now
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

    def _goruntu_sonucunu_sifirla(self) -> None:
        """Yeni test başlarken eski leke ve yırtık kararlarını temizler."""
        self.stain_votes.clear()
        self.tear_votes.clear()
        self.last_alert_defects.clear()
        self.has_stain = False
        self.has_tear = False

    def _modelleri_yukle(self) -> None:
        """Modeller yüklenirken program ekranının donmasını engeller."""

        # Model yükleme uzun sürebildiği için bu fonksiyon ayrı iş parçacığında çalışıyor.
        try:
            self.detector = KusurTespiti()
            self.detector.hazirla()
            self.after(0, self._modeller_hazir)
        except Exception as error:
            self.after(
                0,
                self._durum_yaz,
                f"Model yükleme hatası: {error}",
                COLORS["kirmizi"],
            )

    def _modeller_hazir(self) -> None:
        """Model yüklemesi bitince başlat düğmesini kullanıma açar."""
        self._durum_yaz(
            "Modeller hazır • Canlı testi başlatabilirsiniz",
            COLORS["yesil"],
        )
        self._dugme_durumunu_degistir(self.start_button, True)

    def baslat(self) -> None:
        """Başlat düğmesine basılınca kamerayı ve canlı testi çalıştırır."""
        if self.detector is None:
            messagebox.showwarning("Bekleyin", "Modeller henüz hazır değil.")
            return
        if self.camera_running:
            return
        camera, camera_info = kamera_ac()
        if camera is None or camera_info is None:
            messagebox.showerror(
                "Kamera açılamadı",
                "Geçerli kamera görüntüsü bulunamadı. Kamera bağlantısını kontrol "
                "edip yeniden deneyin.",
            )
            return
        self.camera = camera
        self.camera_info = camera_info
        self.last_frame = None
        self.recent_frames.clear()
        self.laser_off_frame = None
        self.laser_step = "kapali"
        self.laser_active = False
        self.rgb_ready_time = 0.0
        self.rgb_test_id += 1
        self.analysis_id += 1
        self.analysis_running = False
        self._goruntu_sonucunu_sifirla()
        self.has_bump = None
        self.camera_running = True
        self._dugme_durumunu_degistir(self.start_button, False)
        self._dugmeleri_ayarla(True)
        self._lazer_adimini_goster()
        self.camera_status_label.config(text="●  CANLI", fg=COLORS["yesil"])
        self._karti_beklemeye_al(
            "leke", "BEKLİYOR", "İlk model sonucu bekleniyor"
        )
        self._karti_beklemeye_al(
            "yirtik", "BEKLİYOR", "İlk model sonucu bekleniyor"
        )
        self._karti_beklemeye_al(
            "kabariklik", "BEKLİYOR", "İki fotoğraf henüz alınmadı"
        )
        self.decision_label.config(text="BEKLİYOR", fg=COLORS["sari"])
        self.decision_bar.config(bg=COLORS["sari"])
        self._durum_yaz(
            f"Kamera açık: {camera_info} • Lazer kapalı • RGB analizi çalışıyor",
            COLORS["yesil"],
        )
        self._kamerayi_guncelle()

    def lazer_adimini_ilerlet(self) -> None:
        """Lazer kapalı-açık fotoğraf alma adımlarını tek düğmeyle yönetir."""
        if not self.camera_running or self.last_frame is None:
            return
        if self.laser_step == "kapali":
            self._lazer_kapali_fotografi_al()
        elif self.laser_step == "acik":
            self._lazer_acik_fotografi_al()
        elif self.laser_step == "tamam":
            self._rgb_testine_don()
        self._lazer_adimini_goster()
        self._karari_guncelle()

    def _lazer_kapali_fotografi_al(self) -> None:
        # İlk fotoğraf lazer kapalıyken alınır. Bundan sonra RGB sonucu korunur.
        self.laser_off_frame = self._kararli_kareyi_al()
        self.laser_step = "acik"
        self.laser_active = True
        # Lazer moduna geçmeden önce başlamış RGB sonucu daha sonra ekrana gelmesin.
        self.rgb_test_id += 1
        self.analysis_id += 1
        self.analysis_running = False
        self.has_bump = None
        self.laser_button.config(text="LAZER AÇIK FOTOĞRAFI AL")
        self._karti_beklemeye_al(
            "kabariklik",
            "İKİNCİ FOTOĞRAF",
            "Lazeri açın, 1 saniye bekleyip düğmeye tekrar basın",
        )
        self._durum_yaz(
            "Lazer kapalı fotoğraf alındı • Kumaşı oynatmadan lazeri açın",
            COLORS["mor"],
        )

    def _lazer_acik_fotografi_al(self) -> None:
        # İkinci fotoğrafı arka planda karşılaştırırken arayüz donmaz.
        laser_on_frame = self._kararli_kareyi_al()
        self.laser_step = "hesaplaniyor"
        self.laser_button.config(text="KARŞILAŞTIRILIYOR…")
        self._dugme_durumunu_degistir(self.laser_button, False)
        self._karti_beklemeye_al(
            "kabariklik", "HESAPLANIYOR", "İki fotoğraf karşılaştırılıyor"
        )
        threading.Thread(
            target=self._lazer_fotograflarini_isle,
            args=(self.laser_off_frame.copy(), laser_on_frame),
            daemon=True,
        ).start()

    def _rgb_testine_don(self) -> None:
        # Kullanıcı lazeri kapattıktan sonra RGB analizi yeniden başlar.
        self.laser_step = "kapali"
        self.laser_active = False
        self.laser_off_frame = None
        # Lazer sonucu, ölçüm tamamlandığında birleşik kararda gösterilir. RGB'ye
        # dönmek yeni bir kontrol başladığı anlamına geldiği için eski sonuç silinir.
        self.has_bump = None
        self._karti_beklemeye_al(
            "kabariklik",
            "BEKLİYOR",
            "Yeni lazer ölçümü henüz yapılmadı",
        )
        self.recent_frames.clear()
        # Parlak lazer kapatılınca telefon kamerasının pozlaması hemen düzelmeyebilir.
        # Bir saniye bekleyip RGB analizini yeni bir oturum olarak başlatıyorum.
        self.rgb_ready_time = time.monotonic() + 1.0
        self.rgb_test_id += 1
        self.analysis_id += 1
        self.analysis_running = False
        self.last_analysis_time = 0.0
        self.laser_button.config(text="LAZER KAPALI FOTOĞRAFI AL")
        self.stain_votes.clear()
        self.tear_votes.clear()
        self._durum_yaz(
            f"Kamera açık: {self.camera_info} • RGB analizi yeniden hazırlanıyor",
            COLORS["yesil"],
        )
        self.after(1050, self._rgb_hazir_mesaji, self.rgb_test_id)

    def _kararli_kareyi_al(self) -> np.ndarray:
        """Son üç kamera karesini birleştirip daha temiz bir fotoğraf oluşturur."""
        if not self.recent_frames:
            return self.last_frame.copy()
        if len(self.recent_frames) == 1:
            return self.recent_frames[0].copy()
        frames = np.stack(tuple(self.recent_frames), axis=0)
        return np.median(frames, axis=0).astype(np.uint8)

    def _rgb_hazir_mesaji(self, test_id: int) -> None:
        """Lazer sonrasında kamera toparlanınca RGB'nin çalıştığını bildirir."""
        if (
            self.camera_running
            and not self.laser_active
            and test_id == self.rgb_test_id
        ):
            self._durum_yaz(
                f"Kamera açık: {self.camera_info} • RGB analizi çalışıyor",
                COLORS["yesil"],
            )

    def _lazer_fotograflarini_isle(
        self,
        laser_off_frame: np.ndarray,
        laser_on_frame: np.ndarray,
    ) -> None:
        """İki fotoğrafı arka planda karşılaştırır."""
        try:
            result = lazer_fotograflarini_karsilastir(
                laser_off_frame,
                laser_on_frame,
            )
            self.after(0, lambda value=result: self._lazer_sonucunu_goster(value))
        except Exception as error:
            self.after(0, lambda message=str(error): self._lazer_hatasini_goster(message))

    def _lazer_sonucunu_goster(self, result: LazerKarsilastirma) -> None:
        """İki fotoğraftan bulunan kabarıklık sonucunu ekrana yazar."""
        if not self.camera_running or self.laser_step != "hesaplaniyor":
            return
        self.laser_step = "tamam"
        self.has_bump = result.has_bump
        self.laser_button.config(text="LAZERİ KAPAT • RGB TESTİNE DÖN")
        self._dugme_durumunu_degistir(self.laser_button, True)
        self._lazer_adimini_goster()
        self._kart_guncelle(
            "kabariklik",
            result.has_bump,
            f"{result.direction.title()} lazer • Sapma {result.deviation:.2f} / {result.threshold:.2f} px",
        )
        self._durum_yaz(
            "Lazer sonucu hazır • Lazeri kapatıp RGB testine dönün",
            COLORS["yesil"],
        )
        self._karari_guncelle()

    def _lazer_hatasini_goster(self, message: str) -> None:
        """Fotoğraflar uygun değilse lazer açık fotoğrafın yeniden alınmasını ister."""
        if not self.camera_running:
            return
        self.laser_step = "acik"
        self.laser_button.config(text="LAZER AÇIK FOTOĞRAFI TEKRAR AL")
        self._dugme_durumunu_degistir(self.laser_button, True)
        self._lazer_adimini_goster()
        self._karti_beklemeye_al("kabariklik", "TEKRAR DENE", message)
        self._durum_yaz(
            "Lazer çizgisi okunamadı • Kumaşı oynatmadan açık fotoğrafı tekrar alın",
            COLORS["sari"],
        )

    def durdur(self) -> None:
        """Kamerayı güvenli şekilde kapatır ve eski sonuçları temizler."""
        self.camera_running = False
        self.laser_active = False
        self.laser_step = "kapali"
        self.rgb_test_id += 1
        self.analysis_id += 1
        self.analysis_running = False
        self.rgb_ready_time = 0.0
        self.last_frame = None
        self.recent_frames.clear()
        self.laser_off_frame = None
        self._goruntu_sonucunu_sifirla()
        self.has_bump = None
        if self.camera is not None:
            self.camera.release()
        self.camera = None
        self._dugme_durumunu_degistir(self.start_button, True)
        self.laser_button.config(text="LAZER KAPALI FOTOĞRAFI AL")
        self._dugmeleri_ayarla(False)
        self._lazer_adimini_goster()
        self.camera_status_label.config(text="●  KAPALI", fg=COLORS["soluk"])
        for key in self.cards:
            self._karti_beklemeye_al(
                key,
                "BEKLİYOR",
                "Kamera kapalı",
                COLORS["soluk"],
            )
        self.decision_label.config(text="DURDURULDU", fg=COLORS["soluk"])
        self.decision_bar.config(bg=COLORS["soluk"])
        self.display_image = None
        self.image_area.config(
            image="",
            text="Kamera görüntüsü burada gösterilecek",
        )
        self._durum_yaz("Kamera durduruldu", COLORS["sari"])

    def _kamerayi_guncelle(self) -> None:
        """Kameradan sürekli kare alır, ekrana verir ve analizleri sıraya koyar."""
        if not self.camera_running or self.camera is None:
            return
        read_ok, frame = self.camera.read()
        if not read_ok:
            self._durum_yaz("Kameradan kare alınamadı", COLORS["kirmizi"])
            self.after(100, self._kamerayi_guncelle)
            return
        if not kare_gecerli_mi(frame):
            self.bad_frame_count += 1
            if self.bad_frame_count >= 10:
                self._durum_yaz(
                    "Kamera geçici olarak tek renk görüntü veriyor • Bağlantı kontrol ediliyor",
                    COLORS["kirmizi"],
                )
            self.after(100, self._kamerayi_guncelle)
            return
        camera_recovered = self.bad_frame_count > 0
        self.bad_frame_count = 0
        self.last_frame = frame.copy()
        self.recent_frames.append(frame.copy())
        if camera_recovered:
            self._durum_yaz(
                f"Kamera açık: {self.camera_info} • Lazer kapalıyken RGB analizi çalışır",
                COLORS["yesil"],
            )
        # Dikey kamera görüntüsü yalnızca önizlemede çevrilir. Modeller kameradan gelen
        # asıl kareyi kullanmaya devam ettiği için bu seçenek sonuçları değiştirmez.
        now = time.monotonic()
        self._onizlemeyi_goster(frame)
        # Manuel kabarıklık kontrolünde yalnızca kamera görüntüsü gösterilir.
        # RGB modelleri durur ve önceki leke-yırtık sonuçları değiştirilmez.
        if (
            not self.laser_active
            and not self.analysis_running
            and now >= self.rgb_ready_time
            and now - self.last_analysis_time >= ANALYSIS_INTERVAL
        ):
            self.last_analysis_time = now
            self.analysis_running = True
            self.analysis_id += 1
            analysis_id = self.analysis_id
            test_id = self.rgb_test_id
            threading.Thread(
                target=self._kusurlari_kontrol_et,
                args=(frame.copy(), test_id, analysis_id),
                daemon=True,
            ).start()
        self.after(30, self._kamerayi_guncelle)

    def _kusurlari_kontrol_et(
        self,
        frame: np.ndarray,
        test_id: int,
        analysis_id: int,
    ) -> None:
        """Seçilen kamera karesini leke ve yırtık modellerine gönderir."""

        # Model hesabı ayrı iş parçacığında çalıştığı için arayüz kullanılabilir kalıyor.
        try:
            if self.detector is not None:
                result = self.detector.kontrol_et(frame)
                self.after(
                    0,
                    lambda s=result, test_id=test_id: self._kusur_sonucunu_goster(s, test_id),
                )
        except Exception as error:
            self.after(
                0,
                self._goruntu_hatasini_goster,
                f"Görüntü kontrol hatası: {error}",
                test_id,
            )
        finally:
            self.after(0, self._analiz_bitti, analysis_id)

    def _analiz_bitti(self, analysis_id: int) -> None:
        """Son analiz bittiyse yeni bir kareye izin verir."""
        if analysis_id == self.analysis_id:
            self.analysis_running = False

    def _goruntu_hatasini_goster(self, message: str, test_id: int) -> None:
        """Önceki testten kalan bir hatayı ekranda göstermez."""
        if test_id == self.rgb_test_id:
            self._durum_yaz(message, COLORS["kirmizi"])

    def _kusur_sonucunu_goster(
        self,
        result: GoruntuSonucu,
        test_id: int,
    ) -> None:
        """Model sonucunu oylamaya ekler ve ekrandaki kartlara yazar."""
        if (
            not self.camera_running
            or self.laser_active
            or test_id != self.rgb_test_id
        ):
            return
        # Bir kusurun tek karede yanlış çıkması sonucu hemen değiştirmesin diye
        # son birkaç kareden çoğunluk oyu alıyorum.
        self.stain_votes.append(result.has_stain)
        self.tear_votes.append(result.has_tear)
        has_stain = sum(self.stain_votes) >= min(
            REQUIRED_VOTES, len(self.stain_votes)
        )
        has_tear = sum(self.tear_votes) >= min(
            REQUIRED_VOTES, len(self.tear_votes)
        )
        self.has_stain = has_stain
        self.has_tear = has_tear
        stain_description = (
            f"Güven %{result.stain_score * 100:.0f} • "
            f"Oy {sum(self.stain_votes)}/{len(self.stain_votes)}"
        )
        check_text = (
            f"Kontrol %{result.tear_check_score * 100:.0f}"
            if result.tear_checked
            else "Ek kontrol gerekmedi"
        )
        self._kart_guncelle("leke", has_stain, stain_description)
        self._kart_guncelle(
            "yirtik",
            has_tear,
            f"Kutu %{result.tear_score * 100:.0f} • "
            f"{check_text} • "
            f"Oy {sum(self.tear_votes)}/{len(self.tear_votes)}",
        )
        self._karari_guncelle()

    def _karari_guncelle(self) -> None:
        """Bulunan kusurları ekrandaki birleşik karar bölümünde gösterir."""
        # Bu oturumda henüz RGB oyu yoksa leke/yırtık durumu bilinmiyor demektir.
        # Eski RGB sonucu karara katılmaz ve eksik kontrol "NORMAL" gösterilmez.
        rgb_checked = len(self.stain_votes) > 0
        defects = [
            name
            for name, var_mi in (
                ("LEKE", rgb_checked and self.has_stain),
                ("YIRTIK", rgb_checked and self.has_tear),
                ("KABARIKLIK", self.has_bump),
            )
            if var_mi
        ]
        self._kusur_sesini_kontrol_et(defects)
        if defects:
            decision = " + ".join(defects)
            decision_color = COLORS["kirmizi"]
        elif self.laser_active and self.has_bump is None:
            decision = "LAZER TESTİ"
            decision_color = COLORS["sari"]
        elif not rgb_checked:
            decision = "RGB BEKLENİYOR"
            decision_color = COLORS["sari"]
        elif self.has_bump is None:
            decision = "RGB NORMAL"
            decision_color = COLORS["mavi"]
        else:
            decision = "NORMAL"
            decision_color = COLORS["yesil"]
        self.decision_label.config(text=decision, fg=decision_color)
        self.decision_bar.config(bg=decision_color)

    def kapat(self) -> None:
        self.durdur()
        self.destroy()


if __name__ == "__main__":
    KumasApp().mainloop()
