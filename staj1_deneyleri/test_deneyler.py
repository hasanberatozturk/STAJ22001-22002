"""Donanım gerektirmeyen giriş ve sentetik profil kontrolleri."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np
from PIL import Image

from staj1_deneyleri import kamera_kalibrasyon_v2 as kalibrasyon
from staj1_deneyleri import yerel_yukselti_analizi as analiz


class DeneyTestleri(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.data = self.root / "girdi"
        self.data.mkdir()
        self.out = self.root / "sonuc"

    def run_quiet(self, function, args):
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return function(args)

    def images(self, signal=True):
        for prefix in ("duz", "yukselti_10kat"):
            off = np.zeros((200, 300, 3), dtype=np.uint8)
            on = off.copy()
            if signal:
                for x in range(300):
                    y = 95 + (10 if prefix == "yukselti_10kat" and 125 < x < 175 else 0)
                    on[y-3:y+4, x, 0] = 240
            for i in range(1, 4):
                for state, frame in (("kapali", off), ("acik", on)):
                    Image.fromarray(frame).save(self.data / f"{prefix}_lazer_{state}_{i:02d}.jpg")

    def test_object_grid(self):
        for shape in ((8, 6), (9, 7)):
            points = kalibrasyon.nesne_noktalari_olustur(shape, 20)
            self.assertEqual(points.shape, (shape[0] * shape[1], 3))
            np.testing.assert_array_equal(points[1], [20, 0, 0])
            np.testing.assert_array_equal(points[-1], [(shape[0]-1)*20, (shape[1]-1)*20, 0])

    def test_corner_count_required(self):
        with self.assertRaises(SystemExit) as error:
            self.run_quiet(kalibrasyon.ana_program, ["--girdi", str(self.data)])
        self.assertEqual(error.exception.code, 2)

    def test_empty_calibration_no_output(self):
        code = self.run_quiet(kalibrasyon.ana_program, ["--girdi", str(self.data), "--cikti", str(self.out), "--ic-kose", "9", "7"])
        self.assertEqual(code, 1)
        self.assertFalse(self.out.exists())

    def test_missing_images_no_output(self):
        with self.assertRaises(SystemExit):
            self.run_quiet(analiz.ana_program, ["--girdi", str(self.data), "--cikti", str(self.out)])
        self.assertFalse(self.out.exists())

    def test_local_shift_and_zero_repeatability(self):
        self.images()
        self.assertEqual(self.run_quiet(analiz.ana_program, ["--girdi", str(self.data), "--cikti", str(self.out)]), 0)
        result = json.loads((self.out / "wp5_analysis_results.json").read_text(encoding="utf-8"))
        self.assertGreater(result["robust_local_vertical_shift_px"], 5)
        self.assertLess(result["robust_local_vertical_shift_px"], 15)
        self.assertEqual(result["flat_repeatability_px"], 0)
        self.assertIsNone(result["signal_to_repeatability_ratio"])
        report = (self.out / "WP5_SAYISAL_ANALIZ.md").read_text(encoding="utf-8")
        self.assertIn("\n## Analiz çıktısı", report)
        self.assertTrue((self.out / "wp5_analysis_summary.png").is_file())
        self.assertTrue((self.out / "wp5_profiles.csv").is_file())

    def test_existing_output_preserved(self):
        self.images()
        self.out.mkdir()
        marker = self.out / "koru.txt"
        marker.write_text("koru", encoding="utf-8")
        with self.assertRaises(SystemExit):
            self.run_quiet(analiz.ana_program, ["--girdi", str(self.data), "--cikti", str(self.out)])
        self.assertEqual(marker.read_text(encoding="utf-8"), "koru")

    def test_no_laser_signal_rejected(self):
        self.images(signal=False)
        with self.assertRaisesRegex(ValueError, "sinyali"):
            analiz.profile(self.data, "duz", 1)


if __name__ == "__main__":
    unittest.main()
