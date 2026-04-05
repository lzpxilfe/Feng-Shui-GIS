import unittest

from feng_shui_gis.feature_reason_presenter import (
    build_feature_mountain_text,
    build_term_cluster_reason,
    build_term_component_text,
    build_term_display_name,
    collect_term_cluster,
)


class _DummyField:
    def __init__(self, name):
        self._name = name

    def name(self):
        return self._name


class _DummyFields:
    def __init__(self, names):
        self._names = list(names)

    def names(self):
        return list(self._names)

    def __iter__(self):
        for name in self._names:
            yield _DummyField(name)


class _DummyFeature(dict):
    def __init__(self, data, field_names, has_geometry=True):
        super().__init__(data)
        self._fields = _DummyFields(field_names)
        self._has_geometry = has_geometry

    def fields(self):
        return self._fields

    def hasGeometry(self):
        return self._has_geometry


class _DummyLayer:
    def __init__(self, features, field_names):
        self._features = list(features)
        self._fields = _DummyFields(field_names)

    def fields(self):
        return self._fields

    def getFeatures(self):
        return iter(self._features)


class FeatureReasonPresenterContractTests(unittest.TestCase):
    def test_term_display_and_mountain_text_follow_language_contract(self):
        feature = _DummyFeature(
            {
                "term_id": "ansan",
                "term_ko": "안산",
                "term_name": "Ansan",
                "mt_name": "Bukhan-san",
                "mt_dist_m": 120.0,
            },
            ["term_id", "term_ko", "term_name", "mt_name", "mt_dist_m"],
        )
        self.assertEqual(build_term_display_name(feature, "ko"), "안산")
        self.assertEqual(build_term_display_name(feature, "en"), "Ansan")
        self.assertIn("약 120m", build_feature_mountain_text(feature, "ko"))

    def test_term_component_text_includes_score_and_mountain(self):
        feature = _DummyFeature(
            {
                "term_id": "ansan",
                "term_ko": "안산",
                "score": 0.812,
                "mt_name": "Bukhan-san",
                "mt_dist_m": 120.0,
            },
            ["term_id", "term_ko", "score", "mt_name", "mt_dist_m"],
        )
        text = build_term_component_text(feature, "ko")
        self.assertIn("점수=0.812", text)
        self.assertIn("산명=Bukhan-san", text)

    def test_collect_term_cluster_keeps_highest_score_per_term(self):
        features = [
            _DummyFeature({"term_id": "ansan", "parent_id": 1, "score": 0.5}, ["term_id", "parent_id", "score"]),
            _DummyFeature({"term_id": "ansan", "parent_id": 1, "score": 0.7}, ["term_id", "parent_id", "score"]),
            _DummyFeature({"term_id": "myeongdang", "parent_id": 1, "score": 0.8}, ["term_id", "parent_id", "score"]),
        ]
        layer = _DummyLayer(features, ["term_id", "parent_id", "score"])
        cluster = collect_term_cluster(layer, 1)
        self.assertEqual(cluster["ansan"]["score"], 0.7)
        self.assertIn("myeongdang", cluster)

    def test_build_term_cluster_reason_summarizes_parent_cluster(self):
        features = [
            _DummyFeature({"term_id": "hyeol", "parent_id": 1, "score": 0.9, "term_ko": "혈"}, ["term_id", "parent_id", "score", "term_ko"]),
            _DummyFeature({"term_id": "myeongdang", "parent_id": 1, "score": 0.8, "term_ko": "명당"}, ["term_id", "parent_id", "score", "term_ko"]),
            _DummyFeature({"term_id": "ansan", "parent_id": 1, "score": 0.7, "term_ko": "안산"}, ["term_id", "parent_id", "score", "term_ko"]),
        ]
        layer = _DummyLayer(features, ["term_id", "parent_id", "score", "term_ko"])
        reason = build_term_cluster_reason(layer, features[0], "ko")
        self.assertIn("형국 계층 요약", reason)
        self.assertIn("핵심(혈/명당)", reason)


if __name__ == "__main__":
    unittest.main()
