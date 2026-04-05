import unittest

from qgis.core import QgsPointXY

from feng_shui_gis.analysis_dem_utils import (
    azimuth_label,
    direction_mean,
    fmt_num,
    mean_scores,
    offset_point,
    sample_dem,
    sample_ring,
    stddev,
)


class _DummyProvider:
    def __init__(self, values):
        self.values = values

    def sample(self, point, _band):
        key = (round(point.x(), 3), round(point.y(), 3))
        if key not in self.values:
            return None, False
        return self.values[key], True


class AnalysisDemUtilsContractTests(unittest.TestCase):
    def test_sample_dem_returns_float_when_provider_succeeds(self):
        provider = _DummyProvider({(1.0, 2.0): 7})
        self.assertEqual(sample_dem(provider, QgsPointXY(1.0, 2.0)), 7.0)
        self.assertIsNone(sample_dem(provider, QgsPointXY(3.0, 4.0)))

    def test_offset_point_follows_azimuth_convention(self):
        point = offset_point(QgsPointXY(0.0, 0.0), 10.0, 90.0)
        self.assertAlmostEqual(point.x(), 10.0)
        self.assertAlmostEqual(point.y(), 0.0)

    def test_sample_ring_collects_available_samples_only(self):
        provider = _DummyProvider(
            {
                (0.0, 10.0): 1.0,
                (10.0, 0.0): 2.0,
            }
        )
        values = sample_ring(
            provider,
            QgsPointXY(0.0, 0.0),
            10.0,
            [0.0, 90.0, 180.0],
        )
        self.assertEqual(values, [1.0, 2.0])

    def test_mean_scores_and_stddev_handle_empty_and_singleton_values(self):
        self.assertIsNone(mean_scores(None, None))
        self.assertEqual(mean_scores(1.0, None, 3.0), 2.0)
        self.assertIsNone(stddev([]))
        self.assertEqual(stddev([5.0]), 0.0)

    def test_direction_mean_averages_directional_samples(self):
        provider = _DummyProvider(
            {
                (0.0, 10.0): 2.0,
                (-2.588, 9.659): 4.0,
                (2.588, 9.659): 6.0,
            }
        )
        mean = direction_mean(provider, QgsPointXY(0.0, 0.0), 10.0, 0.0)
        self.assertEqual(mean, 4.0)

    def test_format_and_azimuth_labels_match_ui_contract(self):
        self.assertEqual(fmt_num(None), "n/a")
        self.assertEqual(fmt_num(1.23456, digits=2), "1.23")
        self.assertEqual(azimuth_label(None), "ring")
        self.assertEqual(azimuth_label(225.0), "남서")


if __name__ == "__main__":
    unittest.main()
