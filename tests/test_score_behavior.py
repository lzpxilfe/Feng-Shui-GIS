import unittest
import importlib

HAS_QGIS = importlib.util.find_spec("qgis") is not None

if HAS_QGIS:
    from feng_shui_gis.analysis_metrics import (
        binary_classification_metrics,
        distribution_stats,
        score_aspect,
        score_water_distance,
        score_gaussian,
    )
    from feng_shui_gis.analysis_scoring import indicator_contributions, profile_weighted_score
else:  # pragma: no cover - qgis runtime not installed in CI/local env
    pass


class ScoreBehaviorTests(unittest.TestCase):
    @unittest.skipUnless(HAS_QGIS, "QGIS runtime required for analysis scoring behavior tests")
    def test_score_aspect_increases_near_target_for_north(self):
        near = score_aspect(178.0, hemisphere="north")
        far = score_aspect(120.0, hemisphere="north")
        self.assertGreater(near, far)

    @unittest.skipUnless(HAS_QGIS, "QGIS runtime required for analysis scoring behavior tests")
    def test_score_water_distance_penalizes_near_zero_distance(self):
        context = {
            "water_distance_target": 400,
            "water_distance_sigma": 120,
        }
        far = score_water_distance(400.0, context=context)
        very_close = score_water_distance(5.0, context=context)
        self.assertGreater(far, very_close)
        self.assertGreaterEqual(far, 0.1)

    @unittest.skipUnless(HAS_QGIS, "QGIS runtime required for analysis scoring behavior tests")
    def test_profile_weighted_score_is_ratio_of_weighted_inputs(self):
        indicators = {"slope": 0.8, "aspect": 0.6, "water": 0.4}
        profile = {"weights": {"slope": 2.0, "aspect": 1.0}}
        self.assertAlmostEqual(
            profile_weighted_score(indicators, profile),
            (2.0 * 0.8 + 1.0 * 0.6) / 3.0,
        )

    @unittest.skipUnless(HAS_QGIS, "QGIS runtime required for analysis scoring behavior tests")
    def test_indicator_contributions_orders_by_contribution(self):
        indicators = {"a": 0.1, "b": 0.9, "c": 0.5}
        profile = {"weights": {"a": 1.0, "b": 5.0, "c": 2.0}}
        rows = indicator_contributions(indicators, profile)
        self.assertEqual([row["key"] for row in rows], ["b", "c", "a"])

    @unittest.skipUnless(HAS_QGIS, "QGIS runtime required for analysis scoring behavior tests")
    def test_binary_classification_metrics_is_deterministic(self):
        labels = [1, 1, 0, 0]
        scores = [0.9, 0.8, 0.3, 0.2]
        metrics = binary_classification_metrics(labels, scores)
        self.assertEqual(metrics["count"], 4)
        self.assertGreaterEqual(metrics["roc_auc"], 0.99)

    @unittest.skipUnless(HAS_QGIS, "QGIS runtime required for analysis scoring behavior tests")
    def test_distribution_stats_supports_basic_cases(self):
        self.assertEqual(distribution_stats([1, 2, 3]), (2.0, 0.816496580927726))

    @unittest.skipUnless(HAS_QGIS, "QGIS runtime required for analysis scoring behavior tests")
    def test_gaussian_score_is_stable(self):
        self.assertAlmostEqual(score_gaussian(1.0, target=1.0, sigma=1.0), 1.0)
        self.assertLess(score_gaussian(3.0, target=1.0, sigma=1.0), 1.0)


if __name__ == "__main__":
    unittest.main()
