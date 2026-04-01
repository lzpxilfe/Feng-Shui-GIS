import unittest

from qgis.core import QgsPointXY

from feng_shui_gis.analysis_term_links import link_ready_payload


class _DummyFeature(dict):
    pass


class AnalysisTermLinkPayloadContractTests(unittest.TestCase):
    def test_link_ready_payload_builds_smoothed_geometry_metadata(self):
        nodes = [
            _DummyFeature(score=0.8, rank=1),
            _DummyFeature(score=0.7, rank=1),
            _DummyFeature(score=0.9, rank=1),
        ]
        payload = link_ready_payload(
            nodes,
            [QgsPointXY(0, 0), QgsPointXY(10, 5), QgsPointXY(20, 10)],
            spec={"link_type": "outer_wrap"},
            min_link_score=0.4,
            distinct_min_distance=0.1,
            smooth_passes=1,
            to_float=float,
        )
        self.assertIsNotNone(payload)
        self.assertGreater(payload["length_m"], 0.0)
        self.assertGreaterEqual(payload["azimuth"], 0.0)
        self.assertEqual(payload["rank_value"], 1)

    def test_link_ready_payload_fails_closed_when_non_backbone_score_is_too_low(self):
        nodes = [_DummyFeature(score=0.2, rank=2), _DummyFeature(score=0.3, rank=2)]
        payload = link_ready_payload(
            nodes,
            [QgsPointXY(0, 0), QgsPointXY(10, 0)],
            spec={"link_type": "front_arc"},
            min_link_score=0.4,
            distinct_min_distance=0.1,
            smooth_passes=0,
            to_float=float,
        )
        self.assertIsNone(payload)


if __name__ == "__main__":
    unittest.main()
