import math
import unittest

from feng_shui_gis.analysis_metrics import (
    binary_classification_metrics,
    metrics_better,
    raw_calibration_stats,
    score_aspect,
    score_gaussian,
    score_water_distance,
    suppress_near_duplicates,
    trapezoid_auc,
    unique_float_candidates,
)


class _DummyPoint:
    def __init__(self, x_value, y_value):
        self._x = x_value
        self._y = y_value

    def x(self):
        return self._x

    def y(self):
        return self._y


class AnalysisMetricsContractTests(unittest.TestCase):
    def test_metrics_better_uses_metric_priority_order(self):
        baseline = {
            "roc_auc": 0.70,
            "pr_auc": 0.55,
            "best_f1": 0.40,
            "best_youden_j": 0.31,
        }
        candidate = {
            "roc_auc": 0.70,
            "pr_auc": 0.58,
            "best_f1": 0.39,
            "best_youden_j": 0.90,
        }

        self.assertTrue(metrics_better(candidate, baseline))
        self.assertFalse(metrics_better(baseline, candidate))

    def test_unique_float_candidates_deduplicates_and_clamps(self):
        values = [1, "1.0", 1.0000001, -5, 3.2, None, "bad", 9]

        self.assertEqual(
            unique_float_candidates(values, min_value=0.0, max_value=5.0),
            [1.0, 0.0, 3.2, 5.0],
        )

    def test_raw_calibration_stats_separates_positive_and_negative_groups(self):
        rows = [
            {"label": 1, "raw": {"slope": 10.0}},
            {"label": 1, "raw": {"slope": 14.0}},
            {"label": 0, "raw": {"slope": 20.0}},
            {"label": 0, "raw": {"slope": 22.0}},
            {"label": 1, "raw": {"tpi": 0.1}},
        ]

        stats = raw_calibration_stats(rows, "slope")

        self.assertEqual(stats["positive_count"], 2)
        self.assertEqual(stats["negative_count"], 2)
        self.assertAlmostEqual(stats["positive_mean"], 12.0)
        self.assertAlmostEqual(stats["negative_mean"], 21.0)
        self.assertAlmostEqual(stats["positive_stddev"], 2.0)
        self.assertAlmostEqual(stats["negative_stddev"], 1.0)

    def test_score_gaussian_returns_peak_at_target_and_remains_bounded(self):
        self.assertIsNone(score_gaussian(None, 10.0, 2.0))
        self.assertAlmostEqual(score_gaussian(10.0, 10.0, 2.0), 1.0)
        off_target = score_gaussian(14.0, 10.0, 2.0)
        self.assertGreaterEqual(off_target, 0.0)
        self.assertLess(off_target, 1.0)

    def test_score_aspect_handles_wraparound_and_context_sharpness(self):
        self.assertAlmostEqual(score_aspect(180.0, "north"), 1.0)
        self.assertAlmostEqual(score_aspect(0.0, "south"), 1.0)
        wrap_score = score_aspect(
            350.0,
            "south",
            context={"aspect_target": 0.0, "aspect_sharpness": 2.0},
        )
        opposite_score = score_aspect(
            180.0,
            "south",
            context={"aspect_target": 0.0, "aspect_sharpness": 2.0},
        )
        self.assertGreater(wrap_score, opposite_score)
        self.assertGreaterEqual(wrap_score, 0.0)
        self.assertLessEqual(wrap_score, 1.0)

    def test_score_water_distance_requires_context_and_penalizes_too_close(self):
        with self.assertRaises(RuntimeError):
            score_water_distance(80.0, context=None)

        context = {"water_distance_target": 120.0, "water_distance_sigma": 40.0}
        self.assertIsNone(score_water_distance(None, context=context))
        self.assertAlmostEqual(score_water_distance(120.0, context=context), 1.0)
        close_score = score_water_distance(10.0, context=context)
        far_score = score_water_distance(280.0, context=context)
        self.assertGreaterEqual(close_score, 0.1)
        self.assertLessEqual(close_score, 0.5)
        self.assertLess(far_score, 0.01)

    def test_suppress_near_duplicates_keeps_best_ordered_candidates(self):
        candidates = [
            {"label": "a", "point": _DummyPoint(0.0, 0.0), "score": 0.9},
            {"label": "b", "point": _DummyPoint(1.0, 1.0), "score": 0.8},
            {"label": "c", "point": _DummyPoint(5.0, 5.0), "score": 0.7},
            {"label": "d", "point": _DummyPoint(10.0, 10.0), "score": 0.6},
        ]

        selected = suppress_near_duplicates(candidates, min_distance=3.0, keep=3)

        self.assertEqual([row["label"] for row in selected], ["a", "c", "d"])
        distance_ac = math.hypot(
            selected[0]["point"].x() - selected[1]["point"].x(),
            selected[0]["point"].y() - selected[1]["point"].y(),
        )
        self.assertGreater(distance_ac, 3.0)

    def test_trapezoid_auc_clamps_and_ignores_non_increasing_segments(self):
        self.assertAlmostEqual(trapezoid_auc([(0.0, 0.0), (0.5, 0.5), (1.0, 1.0)]), 0.5)
        self.assertAlmostEqual(trapezoid_auc([(0.0, 0.0)]), 0.0)
        self.assertLessEqual(
            trapezoid_auc([(0.0, 0.0), (0.5, 1.5), (0.5, 0.2), (1.0, 1.5)]),
            1.0,
        )

    def test_binary_classification_metrics_returns_expected_thresholds(self):
        labels = [1, 1, 0, 0]
        scores = [0.9, 0.8, 0.4, 0.1]

        metrics = binary_classification_metrics(labels, scores)

        self.assertEqual(metrics["count"], 4)
        self.assertGreater(metrics["roc_auc"], 0.9)
        self.assertGreater(metrics["pr_auc"], 0.9)
        self.assertGreater(metrics["best_f1"], 0.9)
        self.assertAlmostEqual(metrics["best_f1_threshold"], 0.8)
        self.assertAlmostEqual(metrics["best_youden_threshold"], 0.8)

    def test_binary_classification_metrics_handles_empty_or_one_class_inputs(self):
        empty_metrics = binary_classification_metrics([], [])
        one_class_metrics = binary_classification_metrics([1, 1], [0.8, 0.7])

        self.assertEqual(empty_metrics["count"], 0)
        self.assertEqual(empty_metrics["roc_auc"], 0.0)
        self.assertEqual(one_class_metrics["count"], 2)
        self.assertEqual(one_class_metrics["pr_auc"], 0.0)


if __name__ == "__main__":
    unittest.main()
