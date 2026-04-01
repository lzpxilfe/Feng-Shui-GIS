import unittest

from feng_shui_gis.calibration_parameter_search import (
    parameter_candidate_profiles,
    parameter_candidates,
    raw_calibration_stats,
)


class CalibrationParameterSearchTests(unittest.TestCase):
    def test_raw_calibration_stats_separates_positive_and_negative_groups(self):
        rows = [
            {"label": 1, "raw": {"slope": 10.0}},
            {"label": 1, "raw": {"slope": 14.0}},
            {"label": 0, "raw": {"slope": 4.0}},
            {"label": 0, "raw": {"slope": 6.0}},
        ]

        stats = raw_calibration_stats(rows, "slope")

        self.assertEqual(stats["positive_count"], 2)
        self.assertEqual(stats["negative_count"], 2)
        self.assertAlmostEqual(stats["positive_mean"], 12.0)
        self.assertAlmostEqual(stats["negative_mean"], 5.0)

    def test_parameter_candidates_clamps_sigma_floor_and_limits_unique_values(self):
        rows = [
            {"label": 1, "raw": {"slope": 10.0}},
            {"label": 1, "raw": {"slope": 12.0}},
            {"label": 0, "raw": {"slope": 5.0}},
            {"label": 0, "raw": {"slope": 6.0}},
        ]

        candidates = parameter_candidates(
            rows,
            "slope",
            base_target=11.0,
            base_sigma=0.1,
            sigma_floor=0.5,
        )

        self.assertLessEqual(len(candidates["targets"]), 4)
        self.assertLessEqual(len(candidates["sigmas"]), 4)
        self.assertTrue(all(value >= 0.5 for value in candidates["sigmas"]))

    def test_parameter_candidate_profiles_returns_bounded_cross_product(self):
        profile = {
            "weights": {"ridge": 1.0},
            "slope_target": 12.0,
            "slope_sigma": 4.0,
            "tpi_target": 0.2,
            "tpi_sigma": 0.4,
        }
        slope_candidates = {"targets": [10.0, 12.0], "sigmas": [1.0, 2.0]}
        tpi_candidates = {"targets": [0.1, 0.2], "sigmas": [0.3, 0.4]}

        candidates = parameter_candidate_profiles(
            profile,
            slope_candidates,
            tpi_candidates,
            max_candidates=5,
        )

        self.assertEqual(len(candidates), 5)
        self.assertTrue(all(candidate["weights"] == {"ridge": 1.0} for candidate in candidates))
        self.assertTrue(all("slope_target" in candidate for candidate in candidates))


if __name__ == "__main__":
    unittest.main()
