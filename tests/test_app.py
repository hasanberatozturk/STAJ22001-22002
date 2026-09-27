"""Kamera ve model açmadan arayüz, RGB/lazer geçişi ve ses kontrolleri."""

import sys
import tkinter as tk
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import KumasApp
from src.camera import kamera_ac, kare_gecerli_mi
from src.defect_detection import GoruntuSonucu
from src.laser_detection import LazerKarsilastirma


class SahteWidget(dict):
    """Ekran sunucusu olmadan widget ayarlarının değişimini takip eder."""

    def __init__(self, parent, **options):
        super().__init__(state="normal")
        self.update(options)

    def config(self, **options):
        self.update(options)

    def cget(self, name):
        return self[name]

    def winfo_exists(self):
        return True

    def pack(self, **options):
        pass

    def pack_propagate(self, value):
        pass

    def bind(self, event, command):
        pass


class UygulamaTesti(unittest.TestCase):
    def setUp(self):
        # Gerçek uygulama ve ekran kurulum kodunu sahte widget'larla çalıştır.
        # Kamera, model, ses ve gerçek pencere açılmaz.
        self.addCleanup(patch.stopall)
        self.worker_thread = patch("app.threading.Thread").start()
        patch.multiple(
            tk.Tk, __init__=Mock(return_value=None), title=Mock(), geometry=Mock(),
            minsize=Mock(), configure=Mock(), protocol=Mock(), after=Mock(),
        ).start()
        patch.multiple(tk, Frame=SahteWidget, Label=SahteWidget, Button=SahteWidget).start()
        self.app = KumasApp()
        self.app.after = Mock()
        self.app.sound_enabled = False
        self.app.last_frame = np.arange(1800, dtype=np.uint8).reshape(20, 30, 3)

    def test_arayuz_ve_kartlar(self):
        self.assertEqual(set(self.app.cards), {"leke", "yirtik", "kabariklik"})
        self.assertEqual(len(self.app.laser_step_labels), 4)
        self.assertEqual(str(self.app.start_button["state"]), "disabled")
        self.app._kart_guncelle("leke", True, "Test sonucu")
        self.assertEqual(self.app.cards["leke"][0]["text"], "VAR")
        self.assertEqual(self.app.cards["leke"][1]["text"], "Test sonucu")

    def test_lazer_sonrasi_rgb_yeniden_calisir(self):
        self.app.camera_running = True
        self.app.has_stain = True
        self.app.lazer_adimini_ilerlet()
        self.assertEqual(self.app.laser_step, "acik")
        self.assertTrue(self.app.has_stain)  # RGB sonucu lazer boyunca korunmalı.
        self.app.lazer_adimini_ilerlet()
        self.assertEqual(self.app.laser_step, "hesaplaniyor")
        self.app._lazer_sonucunu_goster(
            LazerKarsilastirma(True, 12.0, 50.0, 0.9, 8.0, "yatay")
        )
        self.assertTrue(self.app.has_bump)
        old_test_id = self.app.rgb_test_id
        self.app.lazer_adimini_ilerlet()
        self.assertEqual(self.app.laser_step, "kapali")
        self.assertFalse(self.app.laser_active)
        self.assertIsNone(self.app.has_bump)
        self.assertGreater(self.app.rgb_test_id, old_test_id)
        self.assertFalse(self.app.analysis_running)
        self.assertEqual(len(self.app.stain_votes), 0)
        self.app.after.assert_any_call(1050, self.app._rgb_hazir_mesaji, self.app.rgb_test_id)
        self.app._kusur_sonucunu_goster(
            GoruntuSonucu(0.99, 0.0, True, False), self.app.rgb_test_id
        )
        self.assertTrue(self.app.has_stain)
        self.assertEqual(self.app.decision_label["text"], "LEKE")

    def test_rgb_kontrolu_yokken_normal_gosterilmez(self):
        self.app.camera_running = True
        # RGB oyu yokken yalnız lazer sonucu "NORMAL" sayılmamalı.
        self.app.has_bump = False
        self.app._karari_guncelle()
        self.assertEqual(self.app.decision_label["text"], "RGB BEKLENİYOR")
        self.app._kusur_sonucunu_goster(
            GoruntuSonucu(0.05, 0.0, False, False), self.app.rgb_test_id
        )
        self.assertEqual(self.app.decision_label["text"], "NORMAL")

    def test_rgbye_donuste_eski_leke_karara_katilmaz(self):
        self.app.camera_running = True
        self.app._kusur_sonucunu_goster(
            GoruntuSonucu(0.99, 0.0, True, False), self.app.rgb_test_id
        )
        self.assertEqual(self.app.decision_label["text"], "LEKE")
        self.app.laser_step = "tamam"
        self.app.laser_active = True
        self.app.lazer_adimini_ilerlet()
        self.assertEqual(self.app.decision_label["text"], "RGB BEKLENİYOR")

    def test_eski_rgb_sonucu_ve_analizi_yok_sayilir(self):
        self.app.camera_running = True
        self.app.rgb_test_id = 5
        self.app.analysis_id = 7
        self.app.analysis_running = True
        self.app._kusur_sonucunu_goster(GoruntuSonucu(0.99, 0, True, False), 4)
        self.app._analiz_bitti(6)
        self.assertEqual(len(self.app.stain_votes), 0)
        self.assertTrue(self.app.analysis_running)
        self.app._analiz_bitti(7)
        self.assertFalse(self.app.analysis_running)

    def test_durdurma_eski_sonuclari_temizler(self):
        camera = Mock()
        self.app.camera = camera
        self.app.camera_running = True
        self.app.has_bump = True
        self.app.durdur()
        camera.release.assert_called_once()
        self.assertIsNone(self.app.camera)
        self.assertIsNone(self.app.has_bump)
        self.assertFalse(self.app.camera_running)
        self.assertEqual(self.app.decision_label["text"], "DURDURULDU")

    def test_onizleme_asil_kareyi_degistirmez(self):
        frame = self.app.last_frame.copy()
        self.app.preview_angle = 90
        rotated = self.app._onizleme_icin_cevir(frame)
        self.assertEqual(rotated.shape, (30, 20, 3))
        np.testing.assert_array_equal(frame, self.app.last_frame)

    def test_ayni_kusur_sesi_tekrarlamaz(self):
        self.app.sound_enabled = True
        self.worker_thread.reset_mock()
        with patch("app.time.monotonic", return_value=10.0):
            self.app._kusur_sesini_kontrol_et(["LEKE"])
            self.app._kusur_sesini_kontrol_et(["LEKE"])
        self.worker_thread.assert_called_once()
        self.app._kusur_sesini_kontrol_et([])
        self.assertEqual(self.app.last_alert_defects, set())

    def test_fotograf_son_karelerin_medyanidir(self):
        for value in (10, 200, 30):
            self.app.recent_frames.append(np.full((20, 30, 3), value, np.uint8))
        self.assertTrue(np.all(self.app._kararli_kareyi_al() == 30))


class KameraTesti(unittest.TestCase):
    def test_bos_ve_tek_renk_kare_reddedilir(self):
        self.assertFalse(kare_gecerli_mi(None))
        self.assertFalse(kare_gecerli_mi(np.zeros((0, 0, 3), np.uint8)))
        self.assertFalse(kare_gecerli_mi(np.full((20, 30, 3), 100, np.uint8)))

    def test_basarisiz_kamera_kapatilir_sonraki_denenir(self):
        broken, working = Mock(), Mock()
        broken.isOpened.return_value = False
        working.isOpened.return_value = True
        working.read.return_value = (True, np.arange(1800, dtype=np.uint8).reshape(20, 30, 3))
        with patch("src.camera.CAMERA_SOURCES", ((0, "MSMF"), (1, "DSHOW"))), patch(
            "src.camera.cv2.VideoCapture", side_effect=(broken, working)
        ):
            camera, info = kamera_ac()
        broken.release.assert_called_once()
        self.assertIs(camera, working)
        self.assertEqual(info, "DSHOW/1 • 30x20")


if __name__ == "__main__":
    unittest.main()
