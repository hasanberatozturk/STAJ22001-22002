"""Raspberry Pi dokunmatik WP9 canli operator arayuzu."""

from __future__ import annotations

import json
import shutil
import subprocess
import threading
import time
from collections import deque
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import messagebox

from PIL import Image, ImageTk

from wp9_ortak import KusurMotoru


KOK = Path(__file__).resolve().parent
KAYIT_KOKU = Path.home() / "WP9_KAYITLAR"
KABARIKLIK_KOKU = Path.home() / "WP8_FINAL"
KAMERA_BOYUTU = (2304, 1296)
ONIZLEME_AKIS_BOYUTU = (640, 360)
ONIZLEME_BOYUTU = (620, 350)
ANALIZ_ARALIGI_SANIYE = 1.0
OY_PENCERESI = 3
KABARIKLIK_IZLEME_MS = 750

RENK = {
    "zemin": "#07111f",
    "panel": "#101d30",
    "kart": "#17263d",
    "cizgi": "#29415f",
    "metin": "#f8fafc",
    "ikincil": "#9fb0c5",
    "mavi": "#38bdf8",
    "yesil": "#34d399",
    "kirmizi": "#fb7185",
    "sari": "#fbbf24",
    "mor": "#a78bfa",
}
YAZI_TIPI = "DejaVu Sans"


class Arayuz(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Kumas Kusur Tespit Sistemi - WP9 Canli")
        ekran_genisligi = self.winfo_screenwidth()
        ekran_yuksekligi = self.winfo_screenheight()
        self.portre = ekran_yuksekligi > ekran_genisligi
        self.geometry(f"{ekran_genisligi}x{ekran_yuksekligi}")
        self.onizleme_boyutu = (560, 410) if self.portre else ONIZLEME_BOYUTU
        self.configure(bg="#0b1220")
        self.tam_ekran = True
        self.attributes("-fullscreen", self.tam_ekran)
        self.bind("<F11>", self._tam_ekran_degistir)
        self.bind("<Escape>", self._tam_ekran_degistir)
        self.protocol("WM_DELETE_WINDOW", self._kapat)

        self.motor: KusurMotoru | None = None
        self.kamera = None
        self.canli = False
        self.analiz_suruyor = False
        self.son_analiz_zamani = 0.0
        self.oturum_klasoru: Path | None = None
        self.kabariklik_sonuc: dict | None = None
        self.kabariklik_var: bool | None = None
        self.kabariklik_izleniyor = False
        self.kabariklik_onceki_dosya: Path | None = None
        self.kabariklik_onceki_mtime = 0.0
        self.kabariklik_sureci = None
        self.kabariklik_yeni_sonuc_alindi = False
        self.rgb_sonucu_var = False
        self.son_leke = False
        self.son_yirtik = False
        self.son_skorlar = (0.0, 0.0)
        self.leke_oylari: deque[bool] = deque(maxlen=OY_PENCERESI)
        self.yirtik_oylari: deque[bool] = deque(maxlen=OY_PENCERESI)
        self.son_karar = ""
        self._onizleme_img = None

        self._kur()
        self.after(250, self._model_yukle)

    def _etiket(self, ebeveyn, metin, boyut=14, renk="#dbeafe", kalin=False):
        return tk.Label(
            ebeveyn,
            text=metin,
            bg=ebeveyn["bg"],
            fg=renk,
            font=(YAZI_TIPI, boyut, "bold" if kalin else "normal"),
        )

    def _buton(self, ebeveyn, metin, komut, renk="#2563eb"):
        return tk.Button(
            ebeveyn,
            text=metin,
            command=komut,
            bg=renk,
            fg="white",
            activebackground=renk,
            activeforeground="white",
            relief="flat",
            padx=12,
            pady=11,
            font=(YAZI_TIPI, 11 if self.portre else 12, "bold"),
            cursor="hand2",
            bd=0,
            highlightthickness=0,
        )

    def _kur(self) -> None:
        self.configure(bg=RENK["zemin"])
        ust = tk.Frame(self, bg=RENK["panel"], pady=9 if self.portre else 11)
        ust.pack(fill="x")
        baslik_boyutu = 17 if self.portre else 21
        self._etiket(ust, "KUMAŞ KUSUR KONTROLÜ", baslik_boyutu, RENK["metin"], True).pack()
        self.durum = self._etiket(ust, "Sistem hazırlanıyor…", 10 if self.portre else 11, RENK["mavi"])
        self.durum.pack(pady=(3, 0))

        govde = tk.Frame(self, bg=RENK["zemin"], padx=9 if self.portre else 14, pady=9 if self.portre else 12)
        govde.pack(fill="both", expand=True)

        sol = tk.Frame(govde, bg=RENK["panel"], padx=7, pady=7,
                       highlightbackground=RENK["cizgi"], highlightthickness=1)
        if self.portre:
            sol.config(height=355)
            sol.pack(side="top", fill="x", pady=(0, 9))
            sol.pack_propagate(False)
        else:
            sol.pack(side="left", fill="both", expand=True, padx=(0, 12))
        self.onizleme = tk.Label(
            sol,
            text="CANLI GÖRÜNTÜ\n\nBaşlat düğmesine dokunun",
            bg="#020617",
            fg="#94a3b8",
            font=(YAZI_TIPI, 13 if self.portre else 16, "bold"),
        )
        self.onizleme.pack(fill="both", expand=True)

        sag = tk.Frame(govde, bg=RENK["zemin"])
        if self.portre:
            sag.pack(side="bottom", fill="x")
        else:
            sag.config(width=330)
            sag.pack(side="right", fill="y")
            sag.pack_propagate(False)

        self.kart_degerleri = {}
        kart_alani = tk.Frame(sag, bg=RENK["zemin"])
        kart_alani.pack(fill="x")
        for sira, (anahtar, baslik) in enumerate((
            ("leke", "LEKE"), ("yirtik", "YIRTIK"), ("kabariklik", "KABARIKLIK")
        )):
            kart = tk.Frame(kart_alani, bg=RENK["kart"], padx=6 if self.portre else 12,
                            pady=7 if self.portre else 8,
                            highlightbackground=RENK["cizgi"], highlightthickness=1)
            if self.portre:
                kart.grid(row=0, column=sira, padx=3, sticky="nsew")
                kart_alani.grid_columnconfigure(sira, weight=1)
                self._etiket(kart, baslik, 9, RENK["ikincil"], True).pack()
                deger = self._etiket(kart, "BEKLİYOR", 12, RENK["sari"], True)
                deger.pack(pady=(3, 0))
            else:
                kart.pack(fill="x", pady=(0, 7))
                self._etiket(kart, baslik, 11, RENK["ikincil"], True).pack(side="left")
                deger = self._etiket(kart, "BEKLİYOR", 16, RENK["sari"], True)
                deger.pack(side="right")
            self.kart_degerleri[anahtar] = deger

        self.kabariklik_bilgi = self._etiket(
            sag, "Kabarıklık için lazer testi başlatılmadı", 9, RENK["ikincil"]
        )
        self.kabariklik_bilgi.pack(fill="x", pady=(6, 2))

        karar_karti = tk.Frame(sag, bg=RENK["panel"], padx=10 if self.portre else 12,
                               pady=7 if self.portre else 12,
                               highlightbackground=RENK["cizgi"], highlightthickness=1)
        karar_karti.pack(fill="x", pady=(5 if self.portre else 2, 6 if self.portre else 9))
        self._etiket(karar_karti, "GENEL SONUÇ", 9 if self.portre else 11, RENK["ikincil"], True).pack()
        self.karar = self._etiket(karar_karti, "BEKLİYOR", 20 if self.portre else 25, RENK["sari"], True)
        self.karar.pack(pady=(3 if self.portre else 5, 1 if self.portre else 2))
        self.ayrinti = self._etiket(karar_karti, "Canlı analiz henüz başlamadı", 9 if self.portre else 10, RENK["ikincil"])
        self.ayrinti.pack()

        dugme_alani = tk.Frame(sag, bg=RENK["zemin"])
        dugme_alani.pack(fill="x")
        self.baslat_dugmesi = self._buton(dugme_alani, "CANLI TESTİ\nBAŞLAT", self.canli_baslat, "#047857")
        self.durdur_dugmesi = self._buton(dugme_alani, "CANLI TESTİ\nDURDUR", self.canli_durdur, "#be123c")
        self.durdur_dugmesi.config(state="disabled")
        kabariklik_dugmesi = self._buton(dugme_alani, "LAZER TESTİNİ\nBAŞLAT", self.kabariklik_testi, "#6d28d9")
        kabariklik_oku_dugmesi = self._buton(dugme_alani, "SON LAZER\nSONUCUNU GÖSTER", self.kabariklik_oku, "#0e7490")
        if self.portre:
            for sutun in range(2):
                dugme_alani.grid_columnconfigure(sutun, weight=1)
            self.baslat_dugmesi.grid(row=0, column=0, sticky="nsew", padx=3, pady=3)
            self.durdur_dugmesi.grid(row=0, column=1, sticky="nsew", padx=3, pady=3)
            kabariklik_dugmesi.grid(row=1, column=0, sticky="nsew", padx=3, pady=3)
            kabariklik_oku_dugmesi.grid(row=1, column=1, sticky="nsew", padx=3, pady=3)
        else:
            self.baslat_dugmesi.pack(fill="x", pady=4)
            self.durdur_dugmesi.pack(fill="x", pady=4)
            kabariklik_dugmesi.pack(fill="x", pady=(12, 4))
            kabariklik_oku_dugmesi.pack(fill="x", pady=4)

        alt = tk.Frame(self, bg=RENK["panel"], padx=8 if self.portre else 14, pady=5 if self.portre else 6)
        alt.pack(fill="x")
        alt_metin = "RGB: lazer kapalı  •  Kabarıklık: lazer testi" if self.portre else \
            "Canlı RGB testinde lazer kapalı olmalıdır. Kabarıklık ayrı lazer ölçümüdür."
        self._etiket(
            alt,
            alt_metin,
            8 if self.portre else 9,
            RENK["ikincil"],
        ).pack(side="left")
        self._buton(alt, "ÇIKIŞ", self._kapat, "#881337").pack(side="right")

    def _tam_ekran_degistir(self, _olay=None) -> None:
        self.tam_ekran = not self.tam_ekran
        self.attributes("-fullscreen", self.tam_ekran)

    def _model_yukle(self) -> None:
        def islem():
            try:
                self.motor = KusurMotoru(KOK)
                self.after(0, lambda: self.durum.config(text="Sistem hazır • Canlı testi başlatabilirsiniz", fg=RENK["yesil"]))
            except Exception as exc:
                self.after(0, lambda: self.durum.config(text=f"Model hatasi: {exc}", fg="#f87171"))

        threading.Thread(target=islem, daemon=True).start()

    def canli_baslat(self) -> None:
        if self.motor is None:
            messagebox.showwarning("Bekleyin", "Modeller henuz yuklenmedi.")
            return
        if self.canli:
            return
        try:
            from picamera2 import Picamera2

            self.kamera = Picamera2()
            ayar = self.kamera.create_preview_configuration(
                # Picamera2 adlandirmasinda BGR888 tamponu PIL icin RGB siradadir.
                main={"size": KAMERA_BOYUTU, "format": "BGR888"},
                lores={"size": ONIZLEME_AKIS_BOYUTU, "format": "BGR888"},
                buffer_count=4,
            )
            self.kamera.configure(ayar)
            try:
                self.kamera.set_controls({"AfMode": 0, "LensPosition": 2.50, "AwbEnable": True})
            except Exception:
                pass
            self.kamera.start()
        except Exception as exc:
            self.kamera = None
            messagebox.showerror("Kamera baslatilamadi", f"Picamera2 kamera acilamadi:\n{exc}")
            return

        zaman = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.oturum_klasoru = KAYIT_KOKU / zaman
        (self.oturum_klasoru / "canli_kareler").mkdir(parents=True, exist_ok=True)
        self.leke_oylari.clear()
        self.yirtik_oylari.clear()
        self.rgb_sonucu_var = False
        self.son_karar = ""
        # Ilk pozlama ve beyaz dengesi karara girmeden once otursun.
        self.son_analiz_zamani = time.monotonic() + 1.0
        self.canli = True
        self.analiz_suruyor = False
        self.baslat_dugmesi.config(state="disabled")
        self.durdur_dugmesi.config(state="normal")
        self.durum.config(text="Canlı kamera açık • Otomatik analiz yapılıyor", fg=RENK["yesil"])
        self._kamera_tick()

    def canli_durdur(self) -> None:
        self.canli = False
        kamera = self.kamera
        self.kamera = None
        if kamera is not None:
            try:
                kamera.stop()
                kamera.close()
            except Exception:
                pass
        self.baslat_dugmesi.config(state="normal")
        self.durdur_dugmesi.config(state="disabled")
        self.durum.config(text="Canlı test durduruldu", fg=RENK["sari"])

    def _kamera_tick(self) -> None:
        if not self.canli or self.kamera is None:
            return
        try:
            onizleme_karesi = self.kamera.capture_array("lores")
            onizleme = Image.fromarray(onizleme_karesi)
            onizleme.thumbnail(self.onizleme_boyutu, Image.Resampling.LANCZOS)
            self._onizleme_img = ImageTk.PhotoImage(onizleme)
            self.onizleme.config(image=self._onizleme_img, text="")

            simdi = time.monotonic()
            if not self.analiz_suruyor and simdi - self.son_analiz_zamani >= ANALIZ_ARALIGI_SANIYE:
                self.son_analiz_zamani = simdi
                self.analiz_suruyor = True
                analiz_karesi = Image.fromarray(self.kamera.capture_array("main"))
                threading.Thread(target=self._kareyi_analiz_et, args=(analiz_karesi,), daemon=True).start()
        except Exception as exc:
            self.canli_durdur()
            messagebox.showerror("Kamera hatasi", str(exc))
            return
        self.after(80, self._kamera_tick)

    def _kareyi_analiz_et(self, goruntu: Image.Image) -> None:
        try:
            if self.motor is None or self.oturum_klasoru is None:
                return
            zaman = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            dosya = self.oturum_klasoru / "canli_kareler" / f"kare_{zaman}.jpg"
            goruntu.save(dosya, "JPEG", quality=92)
            kare_sonucu = self.motor.kareyi_incele(dosya)
            sonuc = {
                "dosya": kare_sonucu.dosya,
                "leke_skoru": kare_sonucu.leke_skoru,
                "yirtik_skoru": kare_sonucu.yirtik_skoru,
                "leke_var": kare_sonucu.leke,
                "yirtik_var": kare_sonucu.yirtik,
                "zaman": datetime.now().isoformat(timespec="milliseconds"),
            }
            self.after(0, lambda s=sonuc: self._analiz_sonucunu_isle(s))
        except Exception as exc:
            self.after(0, lambda e=str(exc): self.durum.config(text=f"Analiz hatasi: {e}", fg="#f87171"))
        finally:
            self.analiz_suruyor = False

    def _analiz_sonucunu_isle(self, sonuc: dict) -> None:
        self.leke_oylari.append(bool(sonuc["leke_var"]))
        self.yirtik_oylari.append(bool(sonuc["yirtik_var"]))
        adet = len(self.leke_oylari)
        gerekli = 1 if adet == 1 else 2
        leke = sum(self.leke_oylari) >= gerekli
        yirtik = sum(self.yirtik_oylari) >= gerekli

        for ad, var in (("leke", leke), ("yirtik", yirtik)):
            self.kart_degerleri[ad].config(text="VAR" if var else "YOK", fg=RENK["kirmizi"] if var else RENK["yesil"])

        self.rgb_sonucu_var = True
        self.son_leke = leke
        self.son_yirtik = yirtik
        self.son_skorlar = (sonuc["leke_skoru"], sonuc["yirtik_skoru"])
        self.ayrinti.config(
            text=(
                f"Leke %{sonuc['leke_skoru'] * 100:.0f} ({sum(self.leke_oylari)}/{adet}) | "
                f"Yirtik %{sonuc['yirtik_skoru'] * 100:.0f} ({sum(self.yirtik_oylari)}/{adet})"
            )
        )
        karar = self._genel_karari_guncelle()
        self.durum.config(text="Canlı analiz aktif", fg=RENK["yesil"])
        if karar != self.son_karar and karar != "NORMAL":
            self.bell()
        self.son_karar = karar

        kayit = dict(sonuc)
        kayit.update({
            "anlik_karar": karar,
            "leke_oyu": sum(self.leke_oylari),
            "yirtik_oyu": sum(self.yirtik_oylari),
            "oy_adedi": adet,
        })
        if self.oturum_klasoru is not None:
            with (self.oturum_klasoru / "canli_sonuclar.jsonl").open("a", encoding="utf-8") as akim:
                akim.write(json.dumps(kayit, ensure_ascii=False) + "\n")

    def kabariklik_testi(self) -> None:
        if self.canli:
            self.canli_durdur()
        betik = KOK / "wp8_kabariklik_modulu" / "wp8_cizgi_test_final.sh"
        if not betik.exists():
            messagebox.showerror("Eksik dosya", str(betik))
            return
        mevcut = self._son_kabariklik_dosyasi()
        self.kabariklik_onceki_dosya = mevcut
        self.kabariklik_onceki_mtime = mevcut.stat().st_mtime if mevcut else 0.0
        self.kabariklik_izleniyor = True
        self.kabariklik_yeni_sonuc_alindi = False
        self.kabariklik_var = None
        self.kart_degerleri["kabariklik"].config(text="TESTTE", fg=RENK["mor"])
        self.kabariklik_bilgi.config(text="Lazer testi çalışıyor • Sonuç otomatik aktarılacak", fg=RENK["mor"])
        komut = f"cd '{betik.parent}' && chmod +x '{betik.name}' && ./'{betik.name}'"
        adaylar = [
            ["lxterminal", "--command", f"bash -lc \"{komut}\""],
            ["x-terminal-emulator", "-e", "bash", "-lc", komut],
            ["gnome-terminal", "--", "bash", "-lc", komut],
        ]
        for aday in adaylar:
            if shutil.which(aday[0]):
                self.kabariklik_sureci = subprocess.Popen(aday)
                self.durum.config(text="Lazer testi terminalde açıldı", fg=RENK["mor"])
                self.after(KABARIKLIK_IZLEME_MS, self._kabariklik_sonuc_bekle)
                return
        messagebox.showinfo("Terminal gerekli", f"Terminalde calistirin:\ncd {betik.parent}\n./{betik.name}")

    def kabariklik_oku(self) -> None:
        dosya = self._son_kabariklik_dosyasi()
        if dosya is None:
            messagebox.showinfo("Sonuc yok", "Henuz WP8 kabariklik sonucu bulunamadi.")
            return
        self._kabariklik_dosyasini_isle(dosya)

    def _son_kabariklik_dosyasi(self) -> Path | None:
        dosyalar = list(KABARIKLIK_KOKU.rglob("nihai_sonuc.json"))
        return max(dosyalar, key=lambda p: p.stat().st_mtime) if dosyalar else None

    def _kabariklik_sonuc_bekle(self) -> None:
        if not self.kabariklik_izleniyor:
            return
        dosya = self._son_kabariklik_dosyasi()
        if dosya is not None:
            yeni = (
                dosya != self.kabariklik_onceki_dosya
                or dosya.stat().st_mtime > self.kabariklik_onceki_mtime + 0.01
            )
            if yeni:
                self._kabariklik_dosyasini_isle(dosya)
                self.kabariklik_yeni_sonuc_alindi = True
                self.kabariklik_onceki_dosya = dosya
                self.kabariklik_onceki_mtime = dosya.stat().st_mtime
        if self.kabariklik_sureci is not None and self.kabariklik_sureci.poll() is not None:
            self.kabariklik_izleniyor = False
            if not self.kabariklik_yeni_sonuc_alindi:
                self.kart_degerleri["kabariklik"].config(text="HATA", fg=RENK["kirmizi"])
                self.kabariklik_bilgi.config(text="Test kapandı fakat yeni sonuç bulunamadı", fg=RENK["kirmizi"])
            return
        self.after(KABARIKLIK_IZLEME_MS, self._kabariklik_sonuc_bekle)

    def _kabariklik_dosyasini_isle(self, dosya: Path) -> None:
        try:
            self.kabariklik_sonuc = json.loads(dosya.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            messagebox.showerror("Sonuç okunamadı", str(exc))
            return
        tahmin = str(self.kabariklik_sonuc.get("tahmin", "")).upper()
        if tahmin not in {"KUSUR", "NORMAL"}:
            messagebox.showerror("Geçersiz sonuç", f"Bilinmeyen kabarıklık sonucu: {tahmin or '-'}")
            return
        kabariklik = tahmin == "KUSUR"
        self.kabariklik_var = kabariklik
        self.kart_degerleri["kabariklik"].config(
            text="VAR" if kabariklik else "YOK",
            fg=RENK["kirmizi"] if kabariklik else RENK["yesil"],
        )
        bulunan = self.kabariklik_sonuc.get("bulunan_kanit", "-")
        gerekli = self.kabariklik_sonuc.get("gerekli_kanit", "-")
        self.kabariklik_bilgi.config(
            text=f"Lazer sonucu: {tahmin} • Kanıt {bulunan}/{gerekli}",
            fg=RENK["kirmizi"] if kabariklik else RENK["yesil"],
        )
        self.durum.config(text="Lazer testi sonucu otomatik aktarıldı", fg=RENK["yesil"])
        self._genel_karari_guncelle()

    def _genel_karari_guncelle(self) -> str:
        kusurlar = []
        if self.rgb_sonucu_var and self.son_leke:
            kusurlar.append("LEKE")
        if self.rgb_sonucu_var and self.son_yirtik:
            kusurlar.append("YIRTIK")
        if self.kabariklik_var:
            kusurlar.append("KABARIKLIK")

        if kusurlar:
            karar = " + ".join(kusurlar)
            renk = RENK["kirmizi"]
        elif self.rgb_sonucu_var:
            karar = "NORMAL"
            renk = RENK["yesil"]
        elif self.kabariklik_var is False:
            karar = "LAZER NORMAL"
            renk = RENK["yesil"]
        else:
            karar = "BEKLİYOR"
            renk = RENK["sari"]
        self.karar.config(text=karar, fg=renk)
        return karar

    def _kapat(self) -> None:
        if self.canli:
            self.canli_durdur()
        self.destroy()


if __name__ == "__main__":
    Arayuz().mainloop()
