import unittest

from qgis.core import QgsPointXY

from feng_shui_gis.analysis_term_links import (
    build_term_link_feature,
    build_term_link_reason,
    distinct_points,
    group_term_features,
    path_mean_score,
    polyline_length,
    smooth_polyline,
    term_link_fields,
)


class _DummyGeometry:
    def __init__(self, point=None):
        self._point = point

    def asPoint(self):
        return self._point


class _DummyFeature(dict):
    def __init__(self, data, has_geometry=True, point=None):
        super().__init__(data)
        self._has_geometry = has_geometry
        self._geometry = _DummyGeometry(point)

    def hasGeometry(self):
        return self._has_geometry

    def geometry(self):
        return self._geometry


class AnalysisTermLinksContractTests(unittest.TestCase):
    def test_term_link_fields_expose_expected_schema(self):
        fields = term_link_fields()
        self.assertGreaterEqual(fields.indexFromName("src_id"), 0)
        self.assertGreaterEqual(fields.indexFromName("dst_id"), 0)
        self.assertGreaterEqual(fields.indexFromName("reason_ko"), 0)

    def test_group_term_features_groups_by_parent_and_term_id(self):
        grouped = group_term_features(
            [
                _DummyFeature({"term_id": "hyeol", "parent_id": 1}),
                _DummyFeature({"term_id": "ansan", "parent_id": 1}),
                _DummyFeature({"term_id": "misa", "parent_id": 2}),
                _DummyFeature({"term_id": "", "parent_id": 3}),
            ]
        )
        self.assertIn(1, grouped)
        self.assertIn("hyeol", grouped[1])
        self.assertIn("misa", grouped[2])
        self.assertNotIn(3, grouped)

    def test_build_term_link_reason_uses_shared_explanatory_template(self):
        reason = build_term_link_reason(
            spec_label="Core Axis",
            source_id="jusan",
            target_id="ansan",
            style_term="myeongdang",
            score=0.712,
            length_m=55.4,
            azimuth=180.0,
            azimuth_label=lambda value: "남",
            term_label_ko=lambda term_id: {"jusan": "주산", "ansan": "안산", "myeongdang": "명당"}[term_id],
        )
        self.assertIn("Core Axis 경로 주산→안산", reason)
        self.assertIn("평균점수=0.712", reason)
        self.assertIn("방위=180.0°(남)", reason)

    def test_build_term_link_feature_populates_link_metadata(self):
        feature = build_term_link_feature(
            fields=term_link_fields(),
            smoothed_points=[QgsPointXY(0.0, 0.0), QgsPointXY(10.0, 0.0)],
            parent_id=1,
            rank_value=2,
            score=0.7,
            source={"term_id": "jusan", "culture": "korea", "period": "joseon", "profile": "general"},
            target={"term_id": "ansan", "culture": "", "period": "", "profile": ""},
            spec={"style_term": "myeongdang", "link_type": "core_axis", "label": "Core Axis"},
            length_m=10.0,
            azimuth=90.0,
            azimuth_label=lambda value: "동",
            term_label=lambda term_id, language: term_id,
            term_label_ko=lambda term_id: {"jusan": "주산", "ansan": "안산", "myeongdang": "명당"}[term_id],
        )
        self.assertEqual(feature["term_id"], "myeongdang")
        self.assertEqual(feature["src_id"], "jusan")
        self.assertEqual(feature["dst_id"], "ansan")
        self.assertEqual(feature["culture"], "korea")
        self.assertIn("Core Axis", feature["reason_ko"])

    def test_path_helpers_cover_mean_length_distinct_and_smoothing(self):
        score = path_mean_score(
            [{"score": "0.6"}, {"score": 0.8}, {"score": None}],
            lambda value: None if value is None else float(value),
        )
        self.assertAlmostEqual(score, 0.7)

        points = [QgsPointXY(0.0, 0.0), QgsPointXY(3.0, 4.0)]
        self.assertEqual(polyline_length(points), 5.0)

        deduped = distinct_points(
            [QgsPointXY(0.0, 0.0), QgsPointXY(0.01, 0.01), QgsPointXY(1.0, 1.0)],
            min_distance=0.1,
        )
        self.assertEqual(len(deduped), 2)

        smoothed = smooth_polyline(
            [QgsPointXY(0.0, 0.0), QgsPointXY(1.0, 0.0), QgsPointXY(2.0, 0.0)],
            passes=1,
        )
        self.assertGreater(len(smoothed), 3)


if __name__ == "__main__":
    unittest.main()
