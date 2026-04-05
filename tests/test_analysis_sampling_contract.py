import unittest

from feng_shui_gis.analysis_sampling import negative_sampling_plan


class AnalysisSamplingContractTests(unittest.TestCase):
    def test_negative_sampling_plan_creates_local_and_global_windows(self):
        plan = negative_sampling_plan(
            dem_step=10.0,
            extent_bounds=(0.0, 1000.0, 0.0, 800.0),
            positive_xy=[(200.0, 200.0), (260.0, 280.0)],
            local_padding_factor=1.25,
            local_padding_cells=24.0,
        )
        self.assertGreater(plan["min_distance"], 0.0)
        self.assertGreater(plan["min_negative_separation_sq"], 0.0)
        self.assertEqual(len(plan["search_windows"]), 2)
        local_window = plan["search_windows"][0]
        self.assertLessEqual(local_window[0], 200.0)
        self.assertGreaterEqual(local_window[1], 260.0)


if __name__ == "__main__":
    unittest.main()
