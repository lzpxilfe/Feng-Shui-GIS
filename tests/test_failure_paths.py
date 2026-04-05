import json
import tempfile
import unittest

from feng_shui_gis.analysis_metrics import score_water_distance
from feng_shui_gis.calibration_helpers import split_calibration_rows
from feng_shui_gis.config_loader import _load_file
from feng_shui_gis.profile_catalog import _coerce_local_profile_contract


class FailurePathTests(unittest.TestCase):
    def test_invalid_json_file_is_explicitly_rejected(self):
        with tempfile.NamedTemporaryFile("w+", suffix=".json", delete=False) as handle:
            handle.write("{invalid-json")
            handle.flush()
            invalid_path = handle.name

        with self.assertRaisesRegex(RuntimeError, "Invalid JSON config"):
            _load_file(invalid_path)

    def test_missing_local_profile_schema_is_rejected(self):
        payload = {
            "schema_version": "",
            "profiles": {},
        }
        with tempfile.NamedTemporaryFile("w+", suffix=".json", delete=False) as handle:
            json.dump(payload, handle)
            handle.flush()
            local_path = handle.name

        with self.assertRaisesRegex(RuntimeError, "cannot be empty"):
            _coerce_local_profile_contract(local_path, payload)

    def test_unsupported_local_profile_schema_is_rejected(self):
        payload = {
            "schema_version": "0.0.0",
            "profiles": {},
        }
        with tempfile.NamedTemporaryFile("w+", suffix=".json", delete=False) as handle:
            json.dump(payload, handle)
            handle.flush()
            local_path = handle.name

        with self.assertRaisesRegex(RuntimeError, "unsupported schema_version"):
            _coerce_local_profile_contract(local_path, payload)

    def test_calibration_split_contract_disables_validation_when_small(self):
        rows = [{"label": i % 2, "row_id": i, "raw": {"slope": i}} for i in range(5)]
        fit_rows, eval_rows, plan = split_calibration_rows(
            rows,
            random_seed=7,
            split_ratio=0.8,
            min_fit_count=6,
            min_eval_count=3,
        )

        self.assertFalse(plan["validation_enabled"])
        self.assertEqual(plan["mode"], "single_pool_disabled")
        self.assertEqual(eval_rows, [])
        self.assertEqual(len(fit_rows), 5)

    def test_water_distance_requires_context(self):
        with self.assertRaisesRegex(RuntimeError, "requires a validated context"):
            score_water_distance(100.0, context=None)


if __name__ == "__main__":
    unittest.main()
