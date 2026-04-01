import unittest

from feng_shui_gis.calibration_weight_search import (
    candidate_weight_sets,
    focused_weight_map,
    heuristic_weight_map,
    weight_change_summary,
)


class CalibrationWeightSearchTests(unittest.TestCase):
    def test_heuristic_weight_map_scales_by_quality(self):
        weights = {"ridge": 0.5, "water": 0.5}
        discrimination = {
            "ridge": {"quality": 0.8},
            "water": {"quality": 0.2},
        }

        result = heuristic_weight_map(weights, discrimination)

        self.assertGreater(result["ridge"], result["water"])

    def test_focused_weight_map_boosts_focus_key(self):
        weights = {"ridge": 0.5, "water": 0.5}
        discrimination = {
            "ridge": {"quality": 0.6},
            "water": {"quality": 0.6},
        }

        result = focused_weight_map(weights, discrimination, "ridge")

        self.assertGreater(result["ridge"], result["water"])

    def test_candidate_weight_sets_is_deterministic_for_seed(self):
        weights = {"ridge": 0.5, "water": 0.5}
        discrimination = {
            "ridge": {"quality": 0.8},
            "water": {"quality": 0.2},
        }

        first = candidate_weight_sets(
            weights,
            discrimination,
            random_seed=42,
            trial_count=3,
            focus_limit=2,
        )
        second = candidate_weight_sets(
            weights,
            discrimination,
            random_seed=42,
            trial_count=3,
            focus_limit=2,
        )

        self.assertEqual(first, second)
        self.assertEqual(len(first), 1 + 1 + 2 + 3)

    def test_weight_change_summary_reports_material_changes(self):
        deltas, summary = weight_change_summary(
            {"ridge": 0.5, "water": 0.5},
            {"ridge": 0.7, "water": 0.3},
        )

        self.assertAlmostEqual(deltas["ridge"], 0.2)
        self.assertIn("ridge:+0.200", summary)


if __name__ == "__main__":
    unittest.main()
