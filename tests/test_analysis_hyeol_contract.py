import unittest

from feng_shui_gis.analysis_hyeol import (
    adaptive_spacing_diagnostics,
    combine_hydro_scores,
    evaluate_hyeol_candidate,
    grid_points,
    recommended_hyeol_count,
)


class _DummyExtent:
    def __init__(self, xmin, xmax, ymin, ymax):
        self._xmin = xmin
        self._xmax = xmax
        self._ymin = ymin
        self._ymax = ymax

    def xMinimum(self):
        return self._xmin

    def xMaximum(self):
        return self._xmax

    def yMinimum(self):
        return self._ymin

    def yMaximum(self):
        return self._ymax


class AnalysisHyeolContractTests(unittest.TestCase):
    def test_combine_hydro_scores_prefers_blended_score_when_available(self):
        self.assertAlmostEqual(combine_hydro_scores(0.8, 0.2), 0.62)
        self.assertEqual(combine_hydro_scores(0.8, None), 0.8)
        self.assertEqual(combine_hydro_scores(None, 0.2), 0.2)

    def test_adaptive_spacing_inflates_spacing_when_grid_would_be_too_dense(self):
        diagnostics = adaptive_spacing_diagnostics(
            dem_step=10.0,
            width=4000.0,
            height=2000.0,
            base_step_factor=4.0,
            min_span_divisor=200.0,
            fallback_spacing=2.0,
            max_points=500,
        )
        self.assertGreater(diagnostics["spacing"], 40.0)
        self.assertLessEqual(diagnostics["approx_nodes"], 500)

    def test_recommended_hyeol_count_uses_threshold_bands(self):
        count = recommended_hyeol_count(
            width=1200.0,
            height=800.0,
            spacing=40.0,
            thresholds=[
                {"min_nodes": 600, "count": 9},
                {"min_nodes": 300, "count": 7},
            ],
            default_count=5,
        )
        self.assertEqual(count, 7)

    def test_grid_points_offsets_half_spacing_from_extent_origin(self):
        points = list(grid_points(_DummyExtent(0.0, 100.0, 0.0, 100.0), 50.0))
        self.assertEqual(len(points), 4)
        self.assertEqual((points[0].x(), points[0].y()), (25.0, 25.0))
        self.assertEqual((points[-1].x(), points[-1].y()), (75.0, 75.0))

    def test_evaluate_hyeol_candidate_builds_payload_when_threshold_is_met(self):
        candidate = evaluate_hyeol_candidate(
            point="pt-1",
            center=120.0,
            metrics={
                "tpi_norm": 0.02,
                "dem_water_score": 0.5,
                "form_score": 0.7,
                "long_score": 0.6,
                "convergence": 0.55,
                "sashinsa_score": 0.8,
                "enclosure_index": 0.65,
            },
            water_distance=30.0,
            slope_value=12.0,
            aspect_value=180.0,
            hemisphere="north",
            context={"hyeol_threshold": 0.6},
            profile={"name": "general"},
            tpi_min=-0.1,
            tpi_max=0.1,
            score_profile_slope=lambda value, _profile: 0.7 if value is not None else None,
            score_aspect=lambda value, _hemisphere, context=None: 0.8 if context else 0.0,
            score_profile_tpi=lambda value, _profile: 0.9 if value is not None else None,
            score_water_distance=lambda value, context=None: 0.6 if context else 0.0,
            profile_weighted_score=lambda indicators, _profile: sum(indicators.values()) / len(indicators),
        )
        self.assertIsNotNone(candidate)
        self.assertEqual(candidate["point"], "pt-1")
        self.assertGreater(candidate["score"], 0.6)
        self.assertEqual(candidate["hydro_score"], 0.57)

    def test_evaluate_hyeol_candidate_returns_none_for_out_of_band_tpi(self):
        candidate = evaluate_hyeol_candidate(
            point="pt-1",
            center=120.0,
            metrics={"tpi_norm": 0.4, "dem_water_score": 0.5},
            water_distance=30.0,
            slope_value=12.0,
            aspect_value=180.0,
            hemisphere="north",
            context={"hyeol_threshold": 0.6},
            profile={"name": "general"},
            tpi_min=-0.1,
            tpi_max=0.1,
            score_profile_slope=lambda value, _profile: 0.7,
            score_aspect=lambda value, _hemisphere, context=None: 0.8,
            score_profile_tpi=lambda value, _profile: 0.9,
            score_water_distance=lambda value, context=None: 0.6,
            profile_weighted_score=lambda indicators, _profile: 0.9,
        )
        self.assertIsNone(candidate)


if __name__ == "__main__":
    unittest.main()
