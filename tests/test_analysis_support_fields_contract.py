import unittest

from qgis.core import QgsPointXY

from feng_shui_gis.analysis_support_fields import (
    field_replaced_link_types,
    support_field_shapes,
)


class AnalysisSupportFieldsContractTests(unittest.TestCase):
    def test_support_field_shapes_build_outer_and_inner_enclosures(self):
        shapes = support_field_shapes(
            QgsPointXY(0.0, 0.0),
            front_point=QgsPointXY(0.0, 18.0),
            rear_point=QgsPointXY(0.0, -22.0),
            left_inner_point=QgsPointXY(-10.0, 2.0),
            right_inner_point=QgsPointXY(10.0, 2.0),
            left_outer_point=QgsPointXY(-16.0, 4.0),
            right_outer_point=QgsPointXY(16.0, 4.0),
            score=0.75,
        )
        self.assertIsNotNone(shapes)
        self.assertEqual(set(shapes.keys()), {"sashinsa", "jangpung"})
        self.assertGreater(
            shapes["sashinsa"]["field_width"],
            shapes["jangpung"]["field_width"],
        )
        self.assertEqual(
            shapes["sashinsa"]["ring"][0],
            shapes["sashinsa"]["ring"][-1],
        )

    def test_support_field_shapes_can_fall_back_from_missing_outer_terms(self):
        shapes = support_field_shapes(
            QgsPointXY(0.0, 0.0),
            front_point=QgsPointXY(15.0, 0.0),
            rear_point=QgsPointXY(-12.0, 0.0),
            left_inner_point=QgsPointXY(1.0, 8.0),
            right_inner_point=QgsPointXY(1.0, -8.0),
            score=0.6,
            azimuth=90.0,
        )
        self.assertIsNotNone(shapes)
        self.assertAlmostEqual(shapes["jangpung"]["azimuth"], 90.0, places=2)
        self.assertGreater(
            shapes["sashinsa"]["front_length"],
            shapes["jangpung"]["front_length"],
        )

    def test_field_replaced_link_types_identifies_wrap_and_axis_links(self):
        replaced = field_replaced_link_types()
        self.assertIn("outer_wrap", replaced)
        self.assertIn("inner_wrap", replaced)
        self.assertIn("core_axis", replaced)
        self.assertNotIn("water_flow", replaced)


if __name__ == "__main__":
    unittest.main()
