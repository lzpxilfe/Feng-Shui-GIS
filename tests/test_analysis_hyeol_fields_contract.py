import unittest

from qgis.core import QgsPointXY

from feng_shui_gis.analysis_hyeol_fields import hyeol_field_shape


class AnalysisHyeolFieldsContractTests(unittest.TestCase):
    def test_hyeol_field_shape_opens_toward_front_point(self):
        shape = hyeol_field_shape(
            QgsPointXY(0.0, 0.0),
            front_point=QgsPointXY(0.0, 20.0),
            radius_m=20.0,
            relief_m=6.0,
            score=0.8,
        )
        self.assertIsNotNone(shape)
        self.assertEqual(shape["ring"][0], shape["ring"][-1])
        ys = [point[1] for point in shape["ring"][:-1]]
        self.assertGreater(max(ys), abs(min(ys)))
        self.assertGreater(shape["front_length"], shape["rear_length"])

    def test_hyeol_field_shape_can_fall_back_to_azimuth(self):
        shape = hyeol_field_shape(
            QgsPointXY(0.0, 0.0),
            front_point=None,
            radius_m=16.0,
            relief_m=4.0,
            score=0.6,
            azimuth=90.0,
        )
        self.assertIsNotNone(shape)
        xs = [point[0] for point in shape["ring"][:-1]]
        self.assertGreater(max(xs), abs(min(xs)))
        self.assertAlmostEqual(shape["azimuth"], 90.0, places=2)


if __name__ == "__main__":
    unittest.main()
