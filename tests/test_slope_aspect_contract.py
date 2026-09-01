"""Contract tests for DEM-derived slope and aspect (Horn's method).

Background positions drawn for a null model have no slope or aspect fields, so
they have to be measured off the DEM. The observed sites must then be measured
the same way or the comparison confounds two different estimators.
"""

import math
import unittest

from feng_shui_gis.analysis_dem_utils import sample_slope_aspect
from qgis.core import QgsPointXY


class _PlaneProvider:
    """DEM of a tilted plane: z = ax * x + ay * y + c."""

    def __init__(self, ax=0.0, ay=0.0, c=0.0):
        self.ax = ax
        self.ay = ay
        self.c = c

    def sample(self, point, band):
        return (self.ax * point.x() + self.ay * point.y() + self.c, True)


class _HoleProvider:
    """DEM with a nodata cell offset from the centre."""

    def __init__(self, hole_x, hole_y, tolerance=0.5):
        self.hole = (hole_x, hole_y)
        self.tolerance = tolerance

    def sample(self, point, band):
        if (
            abs(point.x() - self.hole[0]) < self.tolerance
            and abs(point.y() - self.hole[1]) < self.tolerance
        ):
            return (None, False)
        return (point.x() * 0.1, True)


CENTRE = QgsPointXY(100.0, 100.0)
STEP = 10.0


class AspectDirectionTests(unittest.TestCase):
    def test_aspect_points_downhill_in_each_cardinal_direction(self):
        cases = {
            # Rising to the north means the downhill bearing is due south.
            180.0: _PlaneProvider(ay=1.0),
            0.0: _PlaneProvider(ay=-1.0),
            90.0: _PlaneProvider(ax=-1.0),
            270.0: _PlaneProvider(ax=1.0),
        }
        for expected_aspect, provider in cases.items():
            _slope, aspect = sample_slope_aspect(provider, CENTRE, STEP)
            self.assertAlmostEqual(aspect, expected_aspect, delta=0.01)

    def test_diagonal_slope_gives_an_intercardinal_aspect(self):
        # Rising to the north-east, so downhill runs south-west (225 deg).
        _slope, aspect = sample_slope_aspect(
            _PlaneProvider(ax=1.0, ay=1.0), CENTRE, STEP
        )
        self.assertAlmostEqual(aspect, 225.0, delta=0.01)

    def test_aspect_stays_within_the_compass_range(self):
        for ax in (-2.0, -0.5, 0.5, 2.0):
            for ay in (-2.0, -0.5, 0.5, 2.0):
                _slope, aspect = sample_slope_aspect(
                    _PlaneProvider(ax=ax, ay=ay), CENTRE, STEP
                )
                self.assertGreaterEqual(aspect, 0.0)
                self.assertLess(aspect, 360.0)


class SlopeMagnitudeTests(unittest.TestCase):
    def test_unit_gradient_is_forty_five_degrees(self):
        slope, _aspect = sample_slope_aspect(_PlaneProvider(ay=1.0), CENTRE, STEP)
        self.assertAlmostEqual(slope, 45.0, delta=0.01)

    def test_slope_matches_the_analytic_gradient(self):
        for ax, ay in ((0.5, 0.0), (0.0, 0.25), (0.3, 0.4)):
            slope, _aspect = sample_slope_aspect(
                _PlaneProvider(ax=ax, ay=ay), CENTRE, STEP
            )
            expected = math.degrees(math.atan(math.hypot(ax, ay)))
            self.assertAlmostEqual(slope, expected, delta=0.01)

    def test_flat_ground_has_zero_slope_and_undefined_aspect(self):
        slope, aspect = sample_slope_aspect(_PlaneProvider(), CENTRE, STEP)
        self.assertEqual(slope, 0.0)
        self.assertIsNone(aspect)

    def test_slope_is_independent_of_the_constant_offset(self):
        low = sample_slope_aspect(_PlaneProvider(ay=0.5, c=0.0), CENTRE, STEP)
        high = sample_slope_aspect(_PlaneProvider(ay=0.5, c=5000.0), CENTRE, STEP)
        self.assertAlmostEqual(low[0], high[0], places=9)


class RobustnessTests(unittest.TestCase):
    def test_nodata_anywhere_in_the_window_yields_no_estimate(self):
        # Substituting the centre value would flatten the estimate silently; a
        # missing indicator is the honest outcome.
        provider = _HoleProvider(CENTRE.x() + STEP, CENTRE.y() + STEP)
        self.assertEqual(sample_slope_aspect(provider, CENTRE, STEP), (None, None))

    def test_invalid_step_yields_no_estimate(self):
        provider = _PlaneProvider(ay=1.0)
        for step in (0.0, -5.0, None, "x"):
            self.assertEqual(sample_slope_aspect(provider, CENTRE, step), (None, None))

    def test_step_size_does_not_change_a_planar_estimate(self):
        provider = _PlaneProvider(ax=0.2, ay=0.3)
        coarse = sample_slope_aspect(provider, CENTRE, 50.0)
        fine = sample_slope_aspect(provider, CENTRE, 2.0)
        self.assertAlmostEqual(coarse[0], fine[0], places=9)
        self.assertAlmostEqual(coarse[1], fine[1], places=9)


if __name__ == "__main__":
    unittest.main()
