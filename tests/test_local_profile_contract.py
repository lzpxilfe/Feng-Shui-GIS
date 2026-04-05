import os
import json
import tempfile
import unittest

from feng_shui_gis.profile_catalog import (
    _LOCAL_PROFILE_SCHEMA_VERSION,
    load_local_profiles_payload,
    write_local_profiles_registry,
)


def _profile_record():
    return {
        "label": {
            "en": "Test",
            "ko": "테스트",
        },
        "weights": {
            "slope": 1.0,
            "tpi": 1.0,
            "line": 1.0,
            "mountain": 1.0,
            "water": 1.0,
            "open": 1.0,
            "term": 1.0,
            "mt_name": 1.0,
        },
        "slope_target": 30.0,
        "slope_sigma": 6.0,
        "tpi_target": 0.0,
        "tpi_sigma": 1.0,
    }


class LocalProfileContractTests(unittest.TestCase):
    def test_load_local_profiles_payload_accepts_legacy_plain_map(self):
        with tempfile.TemporaryDirectory(
            prefix="feng-shui-local-profile-"
        ) as plugin_dir:
            os.makedirs(os.path.join(plugin_dir, "config"), exist_ok=True)
            payload_path = os.path.join(plugin_dir, "config", "local_profiles.json")
            with open(payload_path, "w", encoding="utf-8") as handle:
                json.dump({"legacy_test": _profile_record()}, handle)

            result = load_local_profiles_payload(base_dir=plugin_dir)
            self.assertEqual(
                result["schema_version"],
                _LOCAL_PROFILE_SCHEMA_VERSION,
            )
            self.assertIn("legacy_test", result["profiles"])

    def test_load_local_profiles_payload_accepts_contract_payload(self):
        with tempfile.TemporaryDirectory(prefix="feng-shui-local-profile-") as plugin_dir:
            os.makedirs(os.path.join(plugin_dir, "config"), exist_ok=True)
            payload_path = os.path.join(plugin_dir, "config", "local_profiles.json")
            payload = {
                "schema_version": _LOCAL_PROFILE_SCHEMA_VERSION,
                "profiles": {
                    "contract_test": _profile_record(),
                },
            }
            with open(payload_path, "w", encoding="utf-8") as handle:
                json.dump(payload, handle)

            result = load_local_profiles_payload(base_dir=plugin_dir)
            self.assertIn("contract_test", result["profiles"])
            self.assertEqual(
                result["schema_version"],
                _LOCAL_PROFILE_SCHEMA_VERSION,
            )

    def test_load_local_profiles_payload_rejects_invalid_schema(self):
        with tempfile.TemporaryDirectory(prefix="feng-shui-local-profile-") as plugin_dir:
            os.makedirs(os.path.join(plugin_dir, "config"), exist_ok=True)
            payload_path = os.path.join(plugin_dir, "config", "local_profiles.json")
            with open(payload_path, "w", encoding="utf-8") as handle:
                json.dump({"schema_version": "0.0.0", "profiles": {}}, handle)

            with self.assertRaises(RuntimeError):
                load_local_profiles_payload(base_dir=plugin_dir)

    def test_write_local_profiles_registry_outputs_contract_shape(self):
        with tempfile.TemporaryDirectory(prefix="feng-shui-local-profile-") as plugin_dir:
            os.makedirs(os.path.join(plugin_dir, "config"), exist_ok=True)
            write_local_profiles_registry(
                {
                    "written_test": _profile_record(),
                },
                base_dir=plugin_dir,
            )
            payload = load_local_profiles_payload(base_dir=plugin_dir)
            self.assertEqual(
                payload["schema_version"],
                _LOCAL_PROFILE_SCHEMA_VERSION,
            )
            self.assertEqual(payload["profiles"]["written_test"]["label"]["en"], "Test")


if __name__ == "__main__":
    unittest.main()
