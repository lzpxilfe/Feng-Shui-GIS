import unittest

from feng_shui_gis.analysis_terrain_rules import (
    clamp_min_order,
    clamp_quantile,
    compute_hydro_min_path_length,
    compute_hydro_spacing,
)


class AnalysisTerrainRulesContractTests(unittest.TestCase):
    def test_compute_hydro_spacing_applies_sampling_budget(self):
        spacing = compute_hydro_spacing(
            dem_step=10.0,
            coarse_spacing=50.0,
            width=1000.0,
            height=1000.0,
            spacing_step_factor=3.0,
            spacing_coarse_factor=0.5,
            spacing_fallback=1.0,
            max_points=100,
        )
        self.assertGreater(spacing, 30.0)

    def test_quantile_and_order_clamps_defaults(self):
        self.assertEqual(clamp_quantile("bad"), 0.86)
        self.assertEqual(clamp_min_order("bad"), 2)
        self.assertEqual(clamp_min_order(0), 1)

    def test_compute_hydro_min_path_length_uses_diag_and_node_factor(self):
        value = compute_hydro_min_path_length(
            width=1000.0,
            height=1000.0,
            spacing=20.0,
            base_spacing_factor=4.0,
            base_diag_ratio=0.006,
            node_spacing_factor=7.0,
        )
        self.assertGreaterEqual(value, 140.0)


if __name__ == "__main__":
    unittest.main()
