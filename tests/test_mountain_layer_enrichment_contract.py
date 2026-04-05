import unittest

from feng_shui_gis.mountain_layer_enrichment import (
    feature_priority,
    resolved_mountain_enrichment_options,
)


class _DummyFeature(dict):
    def __init__(self, fid, data):
        super().__init__(data)
        self._fid = fid

    def id(self):
        return self._fid


class MountainLayerEnrichmentContractTests(unittest.TestCase):
    def test_feature_priority_prefers_rank_then_ridge_then_stream_then_score(self):
        ranked = _DummyFeature(4, {"rank": 2})
        ridge = _DummyFeature(5, {"ridge_rank": 3})
        stream = _DummyFeature(6, {"stream_id": 7})
        scored = _DummyFeature(7, {"fs_score": 0.9})

        self.assertEqual(feature_priority(ranked, {"rank"}), (0, 2, 4))
        self.assertEqual(feature_priority(ridge, {"ridge_rank"}), (1, 3, 5))
        self.assertEqual(feature_priority(stream, {"stream_id"}), (2, 7, 6))
        self.assertEqual(feature_priority(scored, {"fs_score"}), (3, -0.9, 7))

    def test_resolved_mountain_enrichment_options_clamps_and_normalizes_values(self):
        resolved = resolved_mountain_enrichment_options(
            radius_m=-10,
            max_features=999999,
            preferred_language="fr",
        )
        self.assertGreater(resolved["radius_m"], 0)
        self.assertIn(resolved["preferred_language"], ("local", "ko", "en"))
        self.assertGreater(resolved["max_features"], 0)


if __name__ == "__main__":
    unittest.main()
