import unittest

from feng_shui_gis.analysis_dem_metrics import (
    compute_cut_depth,
    compute_dem_water_score,
    compute_enclosure_index,
    compute_form_score,
    compute_long_score,
    compute_roughness,
    compute_sashinsa_score,
    null_dem_metrics,
    relief_statistics,
    sampling_setup,
)


def _score_gaussian(value, target, sigma):
    if value is None:
        return None
    delta = abs(value - target)
    return max(0.0, 1.0 - (delta / max(sigma, 1e-6)))


def _mean_scores(*values):
    valid = [value for value in values if value is not None]
    if not valid:
        return None
    return sum(valid) / len(valid)


class AnalysisDemMetricsContractTests(unittest.TestCase):
    def test_null_dem_metrics_exposes_full_metric_shape(self):
        metrics = null_dem_metrics()
        self.assertIn("form_score", metrics)
        self.assertIn("cut_depth", metrics)
        self.assertTrue(all(value is None for value in metrics.values()))

    def test_sampling_setup_applies_context_multipliers_and_bearing_steps(self):
        state = sampling_setup(
            dem_step=10.0,
            sampling_rules={
                "micro_radius_factor": 2.0,
                "macro_radius_factor": 5.0,
                "macro_bearing_step": 90,
                "micro_bearing_step": 120,
            },
            context={
                "micro_radius_multiplier": 1.5,
                "macro_radius_multiplier": 0.5,
            },
        )
        self.assertEqual(state["micro_radius"], 30.0)
        self.assertEqual(state["macro_radius"], 25.0)
        self.assertEqual(state["macro_bearings"], [0, 90, 180, 270])
        self.assertEqual(state["micro_bearings"], [0, 120, 240])

    def test_relief_statistics_summarize_macro_and_micro_values(self):
        stats = relief_statistics(
            macro_values=[10.0, 16.0, 13.0],
            micro_values=[11.0, 12.0],
            stddev_fn=lambda values: 2.5 if len(values) == 3 else 0.5,
        )
        self.assertEqual(stats["relief"], 6.0)
        self.assertEqual(stats["mean_macro"], 13.0)
        self.assertEqual(stats["std_macro"], 2.5)
        self.assertEqual(stats["std_micro"], 0.5)

    def test_compute_form_score_returns_none_without_full_directional_context(self):
        self.assertIsNone(
            compute_form_score(
                center=10.0,
                relief=20.0,
                back_mean=None,
                front_mean=8.0,
                left_mean=9.0,
                right_mean=9.0,
                dem_rules={
                    "form_back": {"target": 0.1, "sigma": 0.2},
                    "form_front": {"target": 0.1, "sigma": 0.2},
                    "form_side": {"target": 0.0, "sigma": 0.2},
                },
                score_gaussian=_score_gaussian,
                mean_scores=_mean_scores,
            )
        )

    def test_compute_long_score_returns_tpi_norm_and_mean_score(self):
        score, tpi_norm = compute_long_score(
            center=12.0,
            relief=10.0,
            mean_macro=10.0,
            std_micro=1.0,
            std_macro=2.0,
            dem_rules={
                "xue": {"target": 0.2, "sigma": 0.4},
                "hierarchy": {"target": 0.5, "sigma": 0.5},
            },
            score_gaussian=_score_gaussian,
            mean_scores=_mean_scores,
        )
        self.assertEqual(tpi_norm, 0.2)
        self.assertIsNotNone(score)

    def test_compute_dem_water_score_uses_convergence_and_slope_factor(self):
        score, convergence = compute_dem_water_score(
            center=10.0,
            micro_values=[12.0, 11.0, 8.0, 9.0],
            slope_deg=10.0,
            dem_rules={
                "slope_denominator": 40.0,
                "wetness": {"target": 0.5, "sigma": 0.5},
            },
            score_gaussian=_score_gaussian,
        )
        self.assertGreater(score, 0.0)
        self.assertGreater(convergence, 0.0)

    def test_compute_sashinsa_and_enclosure_scores_return_values(self):
        sashinsa = compute_sashinsa_score(
            center=10.0,
            relief=20.0,
            back_mean=14.0,
            front_mean=8.0,
            left_mean=11.0,
            right_mean=11.5,
            sashinsa_rules={
                "back_target_ratio": 0.2,
                "back_sigma": 0.3,
                "front_target_ratio": -0.1,
                "front_sigma": 0.3,
                "side_target_ratio": 0.05,
                "side_sigma": 0.3,
            },
            score_gaussian=_score_gaussian,
        )
        enclosure = compute_enclosure_index(
            center=10.0,
            macro_values=[8.0, 11.0, 12.0, 13.0],
            enclosure_rules={"target_ratio": 0.75, "sigma": 0.5},
            score_gaussian=_score_gaussian,
        )
        self.assertIsNotNone(sashinsa)
        self.assertIsNotNone(enclosure)

    def test_compute_roughness_and_cut_depth_handle_empty_inputs(self):
        self.assertIsNone(compute_roughness(None, 10.0))
        self.assertAlmostEqual(compute_roughness(2.0, 10.0), 0.2)
        self.assertIsNone(compute_cut_depth([], 10.0, 5.0))
        self.assertAlmostEqual(compute_cut_depth([11.0, 15.0], 10.0, 5.0), 1.0)


if __name__ == "__main__":
    unittest.main()
