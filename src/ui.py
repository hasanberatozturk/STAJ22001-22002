"""Ekran yerleşimi, düğmeler ve sonuç kartları; model hesabı burada yapılmaz."""

import tkinter as tk
from collections.abc import Callable

import cv2
import numpy as np
from PIL import Image, ImageTk


COLORS = {
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


class KumasArayuzu(tk.Tk):
    """Ortak ekran parçalarını hazırlar; düğme işlemlerini KumasApp yönetir."""

    def _yazi(
        self,
        parent: tk.Misc,
        text: str,
        size: int = 12,
        color: str | None = None,
        bold: bool = False,
    ) -> tk.Label:
        return tk.Label(
            parent,
            text=text,
            bg=parent["bg"],
            fg=color or COLORS["yazi"],
            font=("Segoe UI", size, "bold" if bold else "normal"),
        )

    def _dugme(
        self,
        parent: tk.Misc,
        text: str,
        command: Callable[[], None],
        color: str,
        text_color: str = "white",
    ) -> tk.Button:
        button = tk.Button(
            parent,
            text=text,
            command=command,
            bg=color,
            fg=text_color,
            relief="flat",
            activebackground=color,
            activeforeground=text_color,
            cursor="hand2",
            borderwidth=0,
            highlightthickness=0,
            disabledforeground="#7f8ba1",
            font=("Segoe UI", 10, "bold"),
            padx=10,
            pady=8,
        )
        button.base_color = color
        button.base_text_color = text_color
        button.fade_id = 0
        button.bind("<Enter>", lambda _event: self._dugmenin_ustune_gelindi(button))
        button.bind("<Leave>", lambda _event: self._dugmeden_cikildi(button))
        return button

    def _dugmenin_ustune_gelindi(self, button: tk.Button) -> None:
        if button["state"] == "normal":
            self._dugme_rengini_degistir(button, self._rengi_ac(button.base_color))

    def _dugmeden_cikildi(self, button: tk.Button) -> None:
        color = button.base_color if button["state"] == "normal" else COLORS["pasif"]
        self._dugme_rengini_degistir(button, color)

    def _dugme_durumunu_degistir(
        self,
        button: tk.Button,
        enabled: bool,
    ) -> None:
        """Pasif düğmeleri renkleriyle birlikte anlaşılır hale getirir."""
        target_color = button.base_color if enabled else COLORS["pasif"]
        button.config(
            state="normal" if enabled else "disabled",
            activebackground=target_color,
        )
        if enabled:
            button.config(fg=button.base_text_color)
        self._dugme_rengini_degistir(button, target_color)

    def _dugme_rengini_degistir(self, button: tk.Button, target_color: str) -> None:
        """Düğmenin rengini kısa adımlarla değiştirerek geçişi yumuşatır."""
        button.fade_id += 1
        current_fade = button.fade_id
        start_color = button.cget("bg")
        step_count = 5

        def siradaki_rengi_goster(step: int) -> None:
            # Fare hızlı hareket ederse eski animasyon yeni rengin üstüne yazmasın.
            if not button.winfo_exists() or current_fade != button.fade_id:
                return
            ratio = step / step_count
            new_color = self._renkleri_karistir(
                start_color,
                target_color,
                ratio,
            )
            button.config(bg=new_color)
            if step < step_count:
                self.after(12, siradaki_rengi_goster, step + 1)

        siradaki_rengi_goster(1)

    @staticmethod
    def _renkleri_karistir(start: str, target: str, ratio: float) -> str:
        """İki onaltılık renk arasında yeni bir renk hesaplar."""
        start_rgb = [int(start[i : i + 2], 16) for i in (1, 3, 5)]
        target_rgb = [int(target[i : i + 2], 16) for i in (1, 3, 5)]
        new_rgb = [
            round(old + (new - old) * ratio)
            for old, new in zip(start_rgb, target_rgb)
        ]
        return "#" + "".join(f"{value:02x}" for value in new_rgb)

    @staticmethod
    def _rengi_ac(color: str) -> str:
        """Fare düğmenin üstündeyken rengi az miktarda açar."""
        red, green, blue = (int(color[i : i + 2], 16) for i in (1, 3, 5))
        return f"#{min(red + 28, 255):02x}{min(green + 28, 255):02x}{min(blue + 28, 255):02x}"

    def _arayuzu_hazirla(self) -> None:
        """Ekranı başlık, görüntü ve sonuç bölümleri halinde oluşturur."""
        self._basligi_hazirla()
        main_panel = tk.Frame(self, bg=COLORS["arka_plan"], padx=14, pady=12)
        main_panel.pack(fill="both", expand=True)
        self._kamera_alanini_hazirla(main_panel)

        side_panel = tk.Frame(main_panel, bg=COLORS["arka_plan"], width=370)
        side_panel.pack(side="right", fill="y")
        side_panel.pack_propagate(False)
        self._karar_alanini_hazirla(side_panel)
        self._kusur_kartlarini_hazirla(side_panel)
        self._kontrolleri_hazirla(side_panel)

    def _basligi_hazirla(self) -> None:
        # Üst bölümde program adı ve o anki çalışma durumu gösteriliyor.
        header = tk.Frame(self, bg=COLORS["panel"], padx=18, pady=10)
        header.pack(fill="x")
        title_row = tk.Frame(header, bg=COLORS["panel"])
        title_row.pack()
        self._yazi(title_row, "KUMAŞ KALİTE ASİSTANI", 21, bold=True).pack(
            side="left"
        )
        self._yazi(
            title_row,
            "  •  RGB + LAZER",
            9,
            COLORS["mavi"],
            True,
        ).pack(side="left", padx=(8, 0), pady=(7, 0))
        self.status_label = self._yazi(header, "Modeller yükleniyor…", 10, COLORS["mavi"])
        self.status_label.pack(pady=(3, 0))

    def _kamera_alanini_hazirla(self, main_panel: tk.Frame) -> None:
        image_card = tk.Frame(
            main_panel,
            bg=COLORS["kenar"],
            padx=1,
            pady=1,
        )
        image_card.pack(side="left", fill="both", expand=True, padx=(0, 16))
        image_header = tk.Frame(image_card, bg=COLORS["panel"], padx=12, pady=7)
        image_header.pack(fill="x")
        self._yazi(image_header, "CANLI GÖRÜNTÜ", 10, COLORS["soluk"], True).pack(
            side="left"
        )
        self.camera_status_label = self._yazi(
            image_header, "●  KAPALI", 9, COLORS["soluk"], True
        )
        self.camera_status_label.pack(side="right")
        self.rotate_button = self._dugme(
            image_header,
            "↻  OTOMATİK",
            self.onizlemeyi_cevir,
            COLORS["kart_ikinci"],
            COLORS["mavi"],
        )
        self.rotate_button.config(font=("Segoe UI", 8, "bold"), padx=7, pady=2)
        self.rotate_button.pack(side="right", padx=(0, 12))
        self.sound_button = self._dugme(
            image_header,
            "♪  SES AÇIK",
            self.sesi_degistir,
            COLORS["kart_ikinci"],
            COLORS["yesil"],
        )
        self.sound_button.config(font=("Segoe UI", 8, "bold"), padx=7, pady=2)
        self.sound_button.pack(side="right", padx=(0, 7))
        self.image_area = tk.Label(
            image_card,
            text="Kamera görüntüsü burada gösterilecek",
            bg=COLORS["goruntu"],
            fg=COLORS["soluk"],
            font=("Segoe UI", 14, "bold"),
        )
        self.image_area.pack(fill="both", expand=True)

    def _karar_alanini_hazirla(self, side_panel: tk.Frame) -> None:
        # En önemli bilgi olan birleşik karar sağ bölümün en üstünde gösteriliyor.
        decision_border = tk.Frame(side_panel, bg=COLORS["kenar"], padx=1, pady=1)
        decision_border.pack(fill="x", pady=(0, 9))
        decision_card = tk.Frame(
            decision_border,
            bg=COLORS["kart_ikinci"],
            padx=14,
            pady=10,
        )
        decision_card.pack(fill="both", expand=True)
        decision_header = tk.Frame(decision_card, bg=COLORS["kart_ikinci"])
        decision_header.pack(fill="x")
        self._yazi(decision_header, "SONUÇ", 10, COLORS["soluk"], True).pack(
            side="left"
        )
        self._yazi(decision_header, "RGB + LAZER", 8, COLORS["mavi"], True).pack(
            side="right"
        )
        self.decision_label = self._yazi(
            decision_card, "BEKLİYOR", 21, COLORS["sari"], True
        )
        self.decision_label.config(anchor="w", justify="left", wraplength=330)
        self.decision_label.pack(anchor="w", pady=(4, 2))
        self._yazi(
            decision_card,
            "Üç kontrolün ortak sonucu",
            8,
            COLORS["soluk"],
        ).pack(anchor="w")
        self.decision_bar = tk.Frame(decision_card, bg=COLORS["sari"], height=3)
        self.decision_bar.pack(fill="x", pady=(8, 0))

    def _kusur_kartlarini_hazirla(self, side_panel: tk.Frame) -> None:
        self._yazi(side_panel, "KUSUR DURUMU", 9, COLORS["soluk"], True).pack(
            anchor="w", pady=(0, 5)
        )

        # Her kusur tek satırda gösterildiği için sonuçlar daha hızlı okunabiliyor.
        self.cards: dict[str, tuple[tk.Label, tk.Label]] = {}
        self.card_bars: dict[str, tk.Frame] = {}
        self.card_icons: dict[str, tk.Label] = {}
        for key, title in (("leke", "LEKE"), ("yirtik", "YIRTIK"), ("kabariklik", "KABARIKLIK")):
            card = tk.Frame(side_panel, bg=COLORS["kenar"], padx=1, pady=1)
            card.pack(fill="x", pady=(0, 6))
            card_body = tk.Frame(card, bg=COLORS["kart"])
            card_body.pack(fill="both", expand=True)
            accent_bar = tk.Frame(card_body, bg=COLORS["sari"], width=4)
            accent_bar.pack(side="left", fill="y")
            accent_bar.pack_propagate(False)
            content = tk.Frame(card_body, bg=COLORS["kart"], padx=11, pady=7)
            content.pack(side="left", fill="both", expand=True)
            top_row = tk.Frame(content, bg=COLORS["kart"])
            top_row.pack(fill="x")
            icon_label = self._yazi(
                top_row, "●", 9, COLORS["sari"], True
            )
            icon_label.pack(side="left")
            self._yazi(top_row, title, 10, COLORS["soluk"], True).pack(
                side="left", padx=(6, 0)
            )
            result_label = self._yazi(top_row, "BEKLİYOR", 13, COLORS["sari"], True)
            result_label.config(anchor="e", justify="right", wraplength=185)
            result_label.pack(side="right")
            description = self._yazi(content, "Henüz ölçülmedi", 8, COLORS["soluk"])
            description.config(anchor="w", justify="left", wraplength=320)
            description.pack(fill="x", pady=(3, 0))
            self.cards[key] = (result_label, description)
            self.card_bars[key] = accent_bar
            self.card_icons[key] = icon_label

    def _kontrolleri_hazirla(self, side_panel: tk.Frame) -> None:
        self._yazi(side_panel, "KABARIKLIK ÖLÇÜMÜ", 9, COLORS["soluk"], True).pack(
            anchor="w", pady=(3, 5)
        )
        step_card = tk.Frame(side_panel, bg=COLORS["kart_ikinci"], padx=10, pady=8)
        step_card.pack(fill="x", pady=(0, 8))
        self.laser_step_labels: list[tk.Label] = []
        for index, name in enumerate(("RGB", "KAPALI", "AÇIK", "SONUÇ"), start=1):
            step = self._yazi(step_card, f"{index}  {name}", 8, COLORS["soluk"], True)
            step.pack(side="left", expand=True)
            self.laser_step_labels.append(step)

        self.start_button = self._dugme(
            side_panel, "CANLI TESTİ BAŞLAT", self.baslat, COLORS["dugme_yesil"]
        )
        self.start_button.pack(fill="x", pady=(0, 5))
        self.laser_button = self._dugme(
            side_panel,
            "LAZER KAPALI FOTOĞRAFI AL",
            self.lazer_adimini_ilerlet,
            COLORS["dugme_mavi"],
        )
        self.laser_button.pack(fill="x", pady=(0, 5))
        self.stop_button = self._dugme(
            side_panel,
            "KAMERAYI DURDUR",
            self.durdur,
            COLORS["kart_ikinci"],
            COLORS["kirmizi"],
        )
        self.stop_button.config(
            highlightthickness=1,
            highlightbackground=COLORS["kirmizi"],
            highlightcolor=COLORS["kirmizi"],
        )
        self.stop_button.pack(fill="x")
        self._dugme_durumunu_degistir(self.start_button, False)
        self._dugmeleri_ayarla(False)
        self._lazer_adimini_goster()

    def _dugmeleri_ayarla(self, enabled: bool) -> None:
        self._dugme_durumunu_degistir(self.stop_button, enabled)
        self._dugme_durumunu_degistir(self.laser_button, enabled)

    def _lazer_adimini_goster(self) -> None:
        """Kullanıcının lazer ölçümünde hangi adımda olduğunu renkle gösterir."""
        step_colors = {
            "kapali": ("mavi", "soluk", "soluk", "soluk"),
            "acik": ("yesil", "yesil", "mavi", "soluk"),
            "hesaplaniyor": ("yesil", "yesil", "yesil", "mavi"),
        }
        colors = step_colors.get(self.laser_step, ("yesil",) * 4)
        if not self.camera_running:
            colors = ("soluk",) * 4
        for label, color in zip(self.laser_step_labels, colors):
            label.config(fg=COLORS[color])

    def onizlemeyi_cevir(self) -> None:
        """Canlı görüntüyü saat yönünde 90 derece çevirir."""
        current_angle = self.preview_angle or 0
        self.preview_angle = (current_angle + 90) % 360
        self.rotate_button.config(text=f"↻  {self.preview_angle}°")

    def _onizleme_icin_cevir(self, frame: np.ndarray) -> np.ndarray:
        """Model karesini değiştirmeden yalnızca ekrandaki görüntüyü döndürür."""
        if self.preview_angle is None:
            height, width = frame.shape[:2]
            self.preview_angle = 90 if height > width else 0
            self.rotate_button.config(text=f"↻  {self.preview_angle}°")

        if self.preview_angle == 90:
            return cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)
        if self.preview_angle == 180:
            return cv2.rotate(frame, cv2.ROTATE_180)
        if self.preview_angle == 270:
            return cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)
        return frame

    def _durum_yaz(self, text: str, color: str) -> None:
        self.status_label.config(text=text, fg=color)

    def _karti_beklemeye_al(
        self,
        key: str,
        result: str,
        description: str,
        color: str | None = None,
    ) -> None:
        """Henüz tamamlanmayan bir kontrolün kartını tek yerden günceller."""
        card_color = color or COLORS["sari"]
        result_label, detail_label = self.cards[key]
        result_label.config(text=result, fg=card_color)
        detail_label.config(text=description)
        self.card_bars[key].config(bg=card_color)
        self.card_icons[key].config(fg=card_color)

    def _kart_guncelle(self, key: str, has_defect: bool, description: str) -> None:
        self._karti_beklemeye_al(
            key,
            "VAR" if has_defect else "YOK",
            description,
            COLORS["kirmizi"] if has_defect else COLORS["yesil"],
        )

    def _onizlemeyi_goster(self, frame: np.ndarray) -> None:
        """Kareyi oranını koruyarak yalnızca ekrana sığdırır."""
        preview_frame = self._onizleme_icin_cevir(frame)
        rgb_frame = cv2.cvtColor(preview_frame, cv2.COLOR_BGR2RGB)
        image = Image.fromarray(rgb_frame)
        # Görüntüyü sabit bir boyuta değil, pencerenin o anki boş alanına sığdırıyorum.
        area_width = max(self.image_area.winfo_width() - 16, 320)
        area_height = max(self.image_area.winfo_height() - 16, 240)
        image.thumbnail(
            (area_width, area_height),
            Image.Resampling.BILINEAR,
        )
        self.display_image = ImageTk.PhotoImage(image)
        self.image_area.config(image=self.display_image, text="")
