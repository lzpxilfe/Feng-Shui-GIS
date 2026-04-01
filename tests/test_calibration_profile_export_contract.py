import json
import os
import tempfile
import unittest
from unittest.mock import patch

from feng_shui_gis.calibration_profile_export import export_calibrated_profile


class CalibrationProfileExportContractTests(unittest.TestCase):
    def test_export_calibrated_profile_writes_snapshot_and_registry_payload(self):
        captured = {}

        def _load_local_profiles_payload(base_dir):
            captured["load_base_dir"] = base_dir
            return {"profiles": {"existing": {"label": {"en": "Existing"}}}}

        def _write_local_profiles_registry(profiles, base_dir):
            captured["profiles"] = dict(profiles)
            captured["write_base_dir"] = base_dir

        with tempfile.TemporaryDirectory() as tmpdir:
            os.makedirs(os.path.join(tmpdir, "config"), exist_ok=True)
            with patch(
                "feng_shui_gis.calibration_profile_export.load_local_profiles_payload",
                _load_local_profiles_payload,
            ), patch(
                "feng_shui_gis.calibration_profile_export.write_local_profiles_registry",
                _write_local_profiles_registry,
            ), patch(
                "feng_shui_gis.calibration_profile_export.profile_label",
                side_effect=lambda key, lang: f"{key}-{lang}",
            ), patch(
                "feng_shui_gis.calibration_profile_export.clear_cache"
            ) as clear_cache:
                info = export_calibrated_profile(
                    {
                        "calibration_applied": True,
                        "profile_key": "ridge",
                        "culture_key": "korea",
                        "period_key": "joseon",
                        "tuned_weights": {"form": 0.4, "water": 0.6},
                        "tuned_profile_parameters": {
                            "slope_target": 7.5,
                            "slope_sigma": 2.0,
                            "tpi_target": -0.03,
                            "tpi_sigma": 0.08,
                        },
                    },
                    stamp="20260401_120000",
                    report_dir=tmpdir,
                    plugin_dir=tmpdir,
                )
                with open(info["profile_export_path"], encoding="utf-8") as handle:
                    payload = json.load(handle)

                self.assertEqual(info["profile_export_status"], "saved")
                self.assertTrue(info["profile_export_path"].endswith("feng_shui_profile_20260401_120000.json"))
                self.assertIn("ridge_korea_joseon_cal_20260401_120000", captured["profiles"])
                self.assertEqual(captured["load_base_dir"], tmpdir)
                self.assertEqual(captured["write_base_dir"], tmpdir)
                clear_cache.assert_called_once()
                self.assertIn("ridge_korea_joseon_cal_20260401_120000", payload)

    def test_export_calibrated_profile_skips_when_not_applied(self):
        info = export_calibrated_profile(
            {"calibration_applied": False},
            stamp="20260401_120000",
            report_dir="/tmp",
            plugin_dir="/tmp",
        )
        self.assertEqual(info["profile_export_status"], "skipped-no-change")


if __name__ == "__main__":
    unittest.main()
