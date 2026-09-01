"""Contract tests for line-of-sight between a site and its named landforms.

Ansan and josan are hills looked at from the site. The term assignment uses
elevation and bearing, which cannot tell whether an intervening ridge hides
the candidate — these tests pin the geometry that closes that gap.
"""

import math
import unittest

from feng_shui_gis.analysis_dem_utils import sample_sight_profile
from feng_shui_gis.analysis_visibility import (
    DEFAULT_OBSERVER_HEIGHT_M,
    EARTH_RADIUS_M,
    curvature_drop_m,
    line_of_sight,
    visibility_summary,
)
from qgis.core import QgsPointXY


class CurvatureTests(unittest.TestCase):
    def test_drop_is_zero_at_the_observer(self):
        self.assertEqual(curvature_drop_m(0.0), 0.0)
        self.assertEqual(curvature_drop_m(-5.0), 0.0)

    def test_drop_matches_the_standard_refracted_value(self):
        # ~6.8 m at 10 km is the textbook figure with k = 0.13.
        self.assertAlmostEqual(curvature_drop_m(10000.0), 6.83, delta=0.05)

    def test_drop_grows_with_the_square_of_distance(self):
        near = curvature_drop_m(1000.0)
        far = curvature_drop_m(2000.0)
        self.assertAlmostEqual(far / near, 4.0, delta=0.01)

    def test_refraction_reduces_the_drop(self):
        self.assertLess(
            curvature_drop_m(10000.0, refraction_k=0.13),
            curvature_drop_m(10000.0, refraction_k=0.0),
        )

    def test_unrefracted_drop_matches_plain_geometry(self):
        distance = 10000.0
        expected = (distance ** 2) / (2.0 * EARTH_RADIUS_M)
        self.assertAlmostEqual(
            curvature_drop_m(distance, refraction_k=0.0), expected, places=6
        )


class LineOfSightTests(unittest.TestCase):
    def test_higher_target_over_flat_ground_is_visible(self):
        result = line_of_sight(
            observer_elev=100.0,
            target_elev=200.0,
            target_distance_m=2000.0,
            profile=[(500.0, 105.0), (1000.0, 108.0), (1500.0, 112.0)],
        )
        self.assertTrue(result["visible"])
        self.assertGreater(result["clearance_m"], 0.0)
        self.assertIsNone(result["blocked_at_m"])

    def test_intervening_ridge_hides_the_target(self):
        result = line_of_sight(
            observer_elev=100.0,
            target_elev=200.0,
            target_distance_m=2000.0,
            profile=[(500.0, 110.0), (1000.0, 400.0), (1500.0, 130.0)],
        )
        self.assertFalse(result["visible"])
        self.assertLess(result["clearance_m"], 0.0)
        self.assertEqual(result["blocked_at_m"], 1000.0)

    def test_required_elevation_is_the_break_even_height(self):
        # Raising the target to required_elev_m should put it exactly on the
        # horizon, and a little above that should make it visible.
        blocked = line_of_sight(
            observer_elev=100.0,
            target_elev=200.0,
            target_distance_m=2000.0,
            profile=[(1000.0, 400.0)],
        )
        self.assertFalse(blocked["visible"])
        lifted = line_of_sight(
            observer_elev=100.0,
            target_elev=blocked["required_elev_m"] + 1.0,
            target_distance_m=2000.0,
            profile=[(1000.0, 400.0)],
        )
        self.assertTrue(lifted["visible"])
        self.assertAlmostEqual(lifted["clearance_m"], 1.0, delta=0.01)

    def test_observer_eye_height_can_decide_a_marginal_sight_line(self):
        profile = [(1000.0, 150.0)]
        common = {
            "observer_elev": 100.0,
            "target_elev": 200.2,
            "target_distance_m": 2000.0,
            "profile": profile,
        }
        from_ground = line_of_sight(observer_height_m=0.0, **common)
        standing = line_of_sight(observer_height_m=DEFAULT_OBSERVER_HEIGHT_M, **common)
        # Standing raises the eye, which lifts the whole sight line and lowers
        # the apparent horizon set by the nearer ridge.
        self.assertGreater(standing["clearance_m"], from_ground["clearance_m"])

    def test_the_highest_intervening_angle_wins_not_the_highest_point(self):
        # A lower but much nearer ridge subtends a larger angle than a taller
        # distant one, so it is the real horizon.
        result = line_of_sight(
            observer_elev=0.0,
            target_elev=300.0,
            target_distance_m=10000.0,
            profile=[(200.0, 120.0), (8000.0, 250.0)],
            observer_height_m=0.0,
        )
        self.assertEqual(result["blocked_at_m"], 200.0)
        self.assertFalse(result["visible"])

    def test_samples_at_or_beyond_the_target_are_ignored(self):
        result = line_of_sight(
            observer_elev=100.0,
            target_elev=200.0,
            target_distance_m=1000.0,
            profile=[(1000.0, 9000.0), (2000.0, 9000.0)],
        )
        self.assertTrue(result["visible"])
        self.assertEqual(result["profile_samples"], 0)

    def test_nodata_and_malformed_samples_are_skipped(self):
        result = line_of_sight(
            observer_elev=100.0,
            target_elev=200.0,
            target_distance_m=2000.0,
            profile=[(500.0, None), (None, 400.0), "junk", (1000.0, 400.0)],
        )
        self.assertEqual(result["profile_samples"], 1)
        self.assertFalse(result["visible"])

    def test_empty_profile_reports_unknown_clearance_rather_than_certainty(self):
        result = line_of_sight(
            observer_elev=100.0, target_elev=200.0, target_distance_m=2000.0
        )
        self.assertTrue(result["visible"])
        self.assertIsNone(result["clearance_m"])
        self.assertEqual(result["profile_samples"], 0)

    def test_curvature_can_hide_a_distant_target(self):
        # A target only just above the observer, far enough out that the Earth
        # itself drops it below the sight line.
        result = line_of_sight(
            observer_elev=0.0,
            target_elev=1.0,
            target_distance_m=30000.0,
            profile=[(15000.0, 0.0)],
            observer_height_m=0.0,
        )
        self.assertFalse(result["visible"])

    def test_angles_are_reported_in_degrees(self):
        result = line_of_sight(
            observer_elev=0.0,
            target_elev=1000.0,
            target_distance_m=1000.0,
            profile=[(500.0, 100.0)],
            observer_height_m=0.0,
        )
        self.assertAlmostEqual(result["target_angle_deg"], 45.0, delta=0.5)
        self.assertAlmostEqual(
            result["horizon_angle_deg"], math.degrees(math.atan(0.2)), delta=0.5
        )

    def test_non_positive_distance_is_rejected(self):
        with self.assertRaises(ValueError):
            line_of_sight(
                observer_elev=1.0, target_elev=2.0, target_distance_m=0.0
            )

    def test_missing_elevations_are_rejected(self):
        with self.assertRaises(ValueError):
            line_of_sight(
                observer_elev=None, target_elev=2.0, target_distance_m=100.0
            )


class VisibilitySummaryTests(unittest.TestCase):
    def test_visible_summary_states_the_clearance(self):
        result = line_of_sight(
            observer_elev=100.0,
            target_elev=200.0,
            target_distance_m=2000.0,
            profile=[(1000.0, 110.0)],
        )
        self.assertIn("조망 가능", visibility_summary(result, "ko"))
        self.assertIn("visible", visibility_summary(result, "en"))

    def test_blocked_summary_names_where_the_horizon_sits(self):
        result = line_of_sight(
            observer_elev=100.0,
            target_elev=200.0,
            target_distance_m=2000.0,
            profile=[(1000.0, 400.0)],
        )
        korean = visibility_summary(result, "ko")
        self.assertIn("차단", korean)
        self.assertIn("1000m", korean)
        self.assertIn("hidden", visibility_summary(result, "en"))

    def test_non_dict_input_yields_empty_text(self):
        self.assertEqual(visibility_summary(None), "")
        self.assertEqual(visibility_summary("nope"), "")


class _RampProvider:
    """Fake DEM whose elevation rises with x, with one ridge spike."""

    def sample(self, point, band):
        x = point.x()
        if 450.0 <= x <= 550.0:
            return 500.0, True
        return x / 10.0, True


class SightProfileSamplingTests(unittest.TestCase):
    def test_profile_excludes_both_endpoints(self):
        profile, distance = sample_sight_profile(
            _RampProvider(), QgsPointXY(0.0, 0.0), QgsPointXY(1000.0, 0.0), 100.0
        )
        self.assertAlmostEqual(distance, 1000.0)
        self.assertTrue(all(0.0 < d < 1000.0 for d, _ in profile))

    def test_profile_picks_up_the_intervening_ridge(self):
        provider = _RampProvider()
        profile, distance = sample_sight_profile(
            provider, QgsPointXY(0.0, 0.0), QgsPointXY(1000.0, 0.0), 50.0
        )
        result = line_of_sight(
            observer_elev=0.0,
            target_elev=100.0,
            target_distance_m=distance,
            profile=profile,
        )
        self.assertFalse(result["visible"])

    def test_step_is_widened_so_long_rays_stay_bounded(self):
        profile, _ = sample_sight_profile(
            _RampProvider(),
            QgsPointXY(0.0, 0.0),
            QgsPointXY(100000.0, 0.0),
            1.0,
            max_samples=32,
        )
        self.assertLessEqual(len(profile), 32)

    def test_zero_length_ray_returns_nothing(self):
        profile, distance = sample_sight_profile(
            _RampProvider(), QgsPointXY(5.0, 5.0), QgsPointXY(5.0, 5.0), 10.0
        )
        self.assertEqual(profile, [])
        self.assertEqual(distance, 0.0)

    def test_invalid_step_falls_back_to_the_sample_budget(self):
        for step in (0.0, -3.0, None, "x"):
            profile, _ = sample_sight_profile(
                _RampProvider(),
                QgsPointXY(0.0, 0.0),
                QgsPointXY(1000.0, 0.0),
                step,
                max_samples=10,
            )
            self.assertTrue(profile, step)
            self.assertLessEqual(len(profile), 10, step)


if __name__ == "__main__":
    unittest.main()
