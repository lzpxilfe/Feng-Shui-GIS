import json
import pathlib
import tempfile
import unittest

from feng_shui_gis import config_loader, profile_catalog


def _valid_profile_payload(profile_key="demo_profile"):
    return {
        "schema_version": 1,
        profile_key: {
            "label": {
                "ko": "데모 프로파일",
                "en": "Demo Profile",
            },
            "weights": {
                "ridge": 0.5,
                "water": 0.5,
            },
            "slope_target": 12.0,
            "slope_sigma": 4.0,
            "tpi_target": 0.2,
            "tpi_sigma": 0.4,
        },
    }


class LocalProfileContractTests(unittest.TestCase):
    def setUp(self):
        self._temp_dir = tempfile.TemporaryDirectory()
        self._temp_path = pathlib.Path(self._temp_dir.name)
        self._original_config_path = config_loader._config_path
        self._original_payload_path = profile_catalog._local_profiles_payload_path

        def _patched_config_path(filename):
            if filename == "local_profiles.json":
                return str(self._temp_path / filename)
            return self._original_config_path(filename)

        config_loader._config_path = _patched_config_path
        profile_catalog._local_profiles_payload_path = lambda: str(
            self._temp_path / "local_profiles.json"
        )
        config_loader.clear_cache()

    def tearDown(self):
        config_loader._config_path = self._original_config_path
        profile_catalog._local_profiles_payload_path = self._original_payload_path
        config_loader.clear_cache()
        self._temp_dir.cleanup()

    def _write_payload(self, payload):
        target = self._temp_path / "local_profiles.json"
        target.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        config_loader.clear_cache()
        return target

    def test_local_profiles_payload_migrates_legacy_schema_less_file(self):
        legacy_payload = _valid_profile_payload("legacy_profile")["legacy_profile"]
        self._write_payload(
            {
                "legacy_profile": legacy_payload,
            }
        )

        payload = profile_catalog.local_profiles_payload()

        self.assertEqual(payload["schema_version"], 1)
        self.assertIn("legacy_profile", payload)

    def test_write_local_profiles_payload_rejects_zero_sum_weights(self):
        payload = _valid_profile_payload()
        payload["demo_profile"]["weights"] = {"ridge": 0.0, "water": 0.0}

        with self.assertRaisesRegex(
            RuntimeError,
            r"local_profiles\.json:demo_profile\.weights must sum to a positive value\.",
        ):
            profile_catalog.write_local_profiles_payload(payload)

    def test_write_local_profiles_payload_rejects_non_positive_sigma(self):
        payload = _valid_profile_payload()
        payload["demo_profile"]["slope_sigma"] = 0.0

        with self.assertRaisesRegex(
            RuntimeError,
            r"local_profiles\.json:demo_profile\.slope_sigma must be greater than 0\.",
        ):
            profile_catalog.write_local_profiles_payload(payload)

    def test_write_local_profiles_payload_rejects_empty_localized_label(self):
        payload = _valid_profile_payload()
        payload["demo_profile"]["label"]["ko"] = ""

        with self.assertRaisesRegex(
            RuntimeError,
            r"Missing text value for 'ko' in local_profiles\.json:demo_profile\.label\.",
        ):
            profile_catalog.write_local_profiles_payload(payload)


if __name__ == "__main__":
    unittest.main()
