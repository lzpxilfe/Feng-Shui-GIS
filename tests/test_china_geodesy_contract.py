"""Contract tests for the Chinese datum and projection helpers.

The reference coordinates are well-known landmarks whose GCJ-02 and BD-09
values are widely published; the tolerances below are metre-scale, which is
the accuracy the published approximation actually offers.
"""

import unittest

from feng_shui_gis.china_geodesy import (
    CHINA_ALBERS_PROJ4,
    bd09_offset_meters,
    bd09_to_gcj02,
    bd09_to_wgs84,
    datum_advisory,
    gcj02_offset_meters,
    gcj02_to_bd09,
    gcj02_to_wgs84,
    in_china_advisory_area,
    out_of_china,
    recommended_projected_crs,
    transform,
    wgs84_to_bd09,
    wgs84_to_gcj02,
)

# Tiananmen, Beijing.
BEIJING_WGS84 = (116.3912757, 39.906217)
BEIJING_GCJ02 = (116.397516, 39.907618)
BEIJING_BD09 = (116.403891, 39.913962)

# The Bund, Shanghai.
SHANGHAI_WGS84 = (121.4907, 31.2412)

# Roughly one degree is 1e-5 deg ~ 1 m, so 1e-5 tolerance is metre-scale.
DEGREE_TOLERANCE = 1e-5


class DatumTransformTests(unittest.TestCase):
    def assertCoordsAlmostEqual(self, actual, expected, tolerance=DEGREE_TOLERANCE):
        self.assertAlmostEqual(actual[0], expected[0], delta=tolerance)
        self.assertAlmostEqual(actual[1], expected[1], delta=tolerance)

    def test_wgs84_to_gcj02_matches_published_reference(self):
        self.assertCoordsAlmostEqual(wgs84_to_gcj02(*BEIJING_WGS84), BEIJING_GCJ02)

    def test_wgs84_to_bd09_matches_published_reference(self):
        self.assertCoordsAlmostEqual(wgs84_to_bd09(*BEIJING_WGS84), BEIJING_BD09)

    def test_gcj02_inverse_round_trips_to_sub_meter(self):
        for source in (BEIJING_WGS84, SHANGHAI_WGS84):
            round_tripped = gcj02_to_wgs84(*wgs84_to_gcj02(*source))
            self.assertCoordsAlmostEqual(round_tripped, source, tolerance=1e-7)

    def test_bd09_inverse_round_trips_to_sub_meter(self):
        # BD-09's own trig approximation is lossy, so the achievable residual
        # here is centimetres rather than the sub-millimetre of pure GCJ-02.
        for source in (BEIJING_WGS84, SHANGHAI_WGS84):
            round_tripped = bd09_to_wgs84(*wgs84_to_bd09(*source))
            self.assertCoordsAlmostEqual(round_tripped, source, tolerance=1e-6)

    def test_bd09_gcj02_pair_round_trips(self):
        gcj = wgs84_to_gcj02(*SHANGHAI_WGS84)
        self.assertCoordsAlmostEqual(bd09_to_gcj02(*gcj02_to_bd09(*gcj)), gcj, 1e-6)

    def test_positions_outside_the_algorithm_box_are_left_untouched(self):
        tokyo = (139.6917, 35.6895)
        london = (-0.1276, 51.5072)
        for position in (tokyo, london):
            self.assertTrue(out_of_china(*position), position)
            self.assertEqual(wgs84_to_gcj02(*position), position)
            self.assertEqual(gcj02_to_wgs84(*position), position)

    def test_algorithm_box_is_wider_than_the_advisory_area(self):
        # The published GCJ-02 box reaches over Seoul, so the raw transform does
        # shift a Korean coordinate. That is a property of the spec, and exactly
        # why the user-facing advisory uses its own narrower gate instead.
        seoul = (126.9780, 37.5665)
        self.assertFalse(out_of_china(*seoul))
        self.assertNotEqual(wgs84_to_gcj02(*seoul), seoul)
        self.assertFalse(in_china_advisory_area(*seoul))

    def test_transform_dispatch_covers_every_supported_pair(self):
        self.assertCoordsAlmostEqual(
            transform(*BEIJING_WGS84, "wgs84", "gcj02"), BEIJING_GCJ02
        )
        self.assertCoordsAlmostEqual(
            transform(*BEIJING_WGS84, "WGS84", "BD09"), BEIJING_BD09
        )
        self.assertEqual(
            transform(*BEIJING_WGS84, "wgs84", "wgs84"), BEIJING_WGS84
        )

    def test_transform_rejects_an_unknown_datum(self):
        with self.assertRaises(ValueError):
            transform(*BEIJING_WGS84, "wgs84", "cgcs2000")


class OffsetMagnitudeTests(unittest.TestCase):
    def test_gcj02_offset_is_hundreds_of_meters_across_china(self):
        # The whole point of the advisory: the error is far larger than the
        # cell size of any DEM this plugin is used with.
        for position in (BEIJING_WGS84, SHANGHAI_WGS84, (113.2644, 23.1291)):
            offset = gcj02_offset_meters(*position)
            self.assertGreater(offset, 100.0, position)
            self.assertLess(offset, 1000.0, position)

    def test_bd09_offset_exceeds_gcj02_offset(self):
        self.assertGreater(
            bd09_offset_meters(*BEIJING_WGS84),
            gcj02_offset_meters(*BEIJING_WGS84),
        )

    def test_offset_vanishes_outside_the_algorithm_box(self):
        self.assertAlmostEqual(gcj02_offset_meters(139.6917, 35.6895), 0.0, places=6)


class ProjectionAdviceTests(unittest.TestCase):
    def test_beijing_maps_to_its_three_degree_belt(self):
        advice = recommended_projected_crs(*BEIJING_WGS84)
        self.assertEqual(advice["authid"], "EPSG:4548")
        self.assertIn("117E", advice["label"])

    def test_belt_selection_tracks_longitude(self):
        # Kashgar sits in the westernmost belt, Harbin far to the east.
        self.assertEqual(recommended_projected_crs(75.99, 39.47)["authid"], "EPSG:4534")
        self.assertEqual(
            recommended_projected_crs(126.53, 45.80)["authid"], "EPSG:4551"
        )

    def test_belt_codes_stay_inside_the_epsg_block(self):
        # Sweeping a single latitude crosses the advisory exclusions, so only
        # the positions that do produce advice are checked here.
        seen = 0
        for lon in range(74, 136):
            advice = recommended_projected_crs(float(lon), 35.0)
            if advice is None:
                continue
            seen += 1
            code = int(advice["authid"].split(":")[1])
            self.assertGreaterEqual(code, 4534)
            self.assertLessEqual(code, 4554)
        self.assertGreater(seen, 40)

    def test_belt_block_endpoints_are_reachable(self):
        self.assertEqual(recommended_projected_crs(74.0, 39.0)["authid"], "EPSG:4534")
        self.assertEqual(recommended_projected_crs(135.0, 48.0)["authid"], "EPSG:4554")

    def test_wide_extents_step_up_to_six_degree_then_equal_area(self):
        six_degree = recommended_projected_crs(*BEIJING_WGS84, extent_width_deg=4.0)
        self.assertIn("Gauss-Kruger CM", six_degree["label"])
        self.assertNotIn("3-degree", six_degree["label"])

        albers = recommended_projected_crs(*BEIJING_WGS84, extent_width_deg=12.0)
        self.assertEqual(albers["proj4"], CHINA_ALBERS_PROJ4)

    def test_no_advice_outside_china(self):
        self.assertIsNone(recommended_projected_crs(126.9780, 37.5665))


class DatumAdvisoryTests(unittest.TestCase):
    def test_no_advisory_outside_china(self):
        self.assertIsNone(datum_advisory(center_lon=126.978, center_lat=37.5665))

    def test_advisory_reports_the_shift_in_dem_cells(self):
        advisory = datum_advisory(
            center_lon=BEIJING_WGS84[0],
            center_lat=BEIJING_WGS84[1],
            dem_cell_size_m=30.0,
        )
        self.assertGreater(advisory["cells_shifted"], 10.0)
        self.assertEqual(advisory["severity"], "critical")
        self.assertEqual(advisory["recommended_crs"]["authid"], "EPSG:4548")

    def test_coarse_dem_downgrades_severity_but_still_warns(self):
        advisory = datum_advisory(
            center_lon=BEIJING_WGS84[0],
            center_lat=BEIJING_WGS84[1],
            dem_cell_size_m=250.0,
        )
        self.assertLess(advisory["cells_shifted"], 10.0)
        self.assertEqual(advisory["severity"], "warning")

    def test_unknown_cell_size_still_reports_the_offset(self):
        advisory = datum_advisory(
            center_lon=BEIJING_WGS84[0], center_lat=BEIJING_WGS84[1]
        )
        self.assertIsNone(advisory["cells_shifted"])
        self.assertEqual(advisory["severity"], "info")
        self.assertGreater(advisory["gcj02_offset_m"], 100.0)

    def test_malformed_cell_size_does_not_raise(self):
        for cell_size in ("", "abc", None, 0):
            advisory = datum_advisory(
                center_lon=BEIJING_WGS84[0],
                center_lat=BEIJING_WGS84[1],
                dem_cell_size_m=cell_size,
            )
            self.assertEqual(advisory["severity"], "info", cell_size)


class AdvisoryAreaTests(unittest.TestCase):
    def test_advisory_area_covers_mainland_but_not_neighbours(self):
        self.assertTrue(in_china_advisory_area(*BEIJING_WGS84))
        self.assertTrue(in_china_advisory_area(*SHANGHAI_WGS84))
        self.assertFalse(in_china_advisory_area(126.9780, 37.5665))
        self.assertFalse(in_china_advisory_area(139.6917, 35.6895))


if __name__ == "__main__":
    unittest.main()
