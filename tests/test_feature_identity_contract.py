import unittest

from feng_shui_gis.feature_identity import (
    duplicate_feature_uids,
    feature_uid,
    normalize_change_uids,
    uid_match_summary,
)


class _DummyFields:
    def __init__(self, names):
        self._names = list(names)

    def names(self):
        return list(self._names)


class _DummyGeometry:
    def __init__(self, wkb):
        self._wkb = wkb

    def asWkb(self):
        return self._wkb


class _DummyFeature:
    def __init__(self, attrs, fid, geometry=None):
        self._attrs = dict(attrs)
        self._fid = fid
        self._geometry = geometry

    def fields(self):
        return _DummyFields(self._attrs.keys())

    def __getitem__(self, key):
        return self._attrs[key]

    def hasGeometry(self):
        return self._geometry is not None

    def geometry(self):
        return self._geometry

    def id(self):
        return self._fid


class _DummyLayer:
    def __init__(self, features):
        self._features = list(features)

    def getFeatures(self):
        return list(self._features)


class FeatureIdentityContractTests(unittest.TestCase):
    def test_feature_uid_ignores_derived_fields_when_hashing(self):
        geometry = _DummyGeometry(b"same-geometry")
        base_feature = _DummyFeature(
            {"name": "Tomb A", "region": "hanseong"},
            fid=1,
            geometry=geometry,
        )
        enriched_feature = _DummyFeature(
            {
                "name": "Tomb A",
                "region": "hanseong",
                "fs_score": 0.91,
                "mt_name": "Bukhan-san",
                "cmp_delta": 0.33,
                "cal_score": 0.77,
            },
            fid=9,
            geometry=geometry,
        )

        self.assertEqual(feature_uid(base_feature), feature_uid(enriched_feature))

    def test_feature_uid_prefers_persisted_feature_uid_without_reprefixing(self):
        feature = _DummyFeature(
            {"feature_uid": "site_uid:alpha-01", "name": "Alpha"},
            fid=1,
        )

        self.assertEqual(feature_uid(feature), "site_uid:alpha-01")

    def test_uid_match_summary_reports_ambiguous_and_missing_uids(self):
        layer = _DummyLayer(
            [
                _DummyFeature({"feature_uid": "uid:a"}, fid=1),
                _DummyFeature({"feature_uid": "uid:a"}, fid=2),
                _DummyFeature({"feature_uid": "uid:b"}, fid=3),
            ]
        )

        summary = uid_match_summary(layer, ["uid:a", "uid:b", "uid:missing"])

        self.assertEqual(summary["feature_ids"], [3])
        self.assertEqual(summary["present"], ["uid:b"])
        self.assertEqual(summary["missing"], ["uid:missing"])
        self.assertEqual(summary["ambiguous"], ["uid:a"])

    def test_duplicate_feature_uids_lists_reused_identifiers(self):
        layer = _DummyLayer(
            [
                _DummyFeature({"feature_uid": "uid:a"}, fid=1),
                _DummyFeature({"feature_uid": "uid:a"}, fid=2),
                _DummyFeature({"feature_uid": "uid:b"}, fid=3),
            ]
        )

        self.assertEqual(duplicate_feature_uids(layer), ["uid:a"])

    def test_normalize_change_uids_keeps_only_non_empty_feature_uids(self):
        rows = [
            {"feature_uid": "uid:a", "feature_id": 10},
            {"feature_uid": "uid:a", "feature_id": 11},
            {"feature_id": 12},
            {"feature_id": 13, "feature_uid": ""},
            {},
        ]

        self.assertEqual(normalize_change_uids(rows), ["uid:a"])

    def test_normalize_change_uids_drops_rows_without_feature_uid(self):
        rows = [
            {"feature_id": 12},
            {},
            {"feature_uid": "   "},
        ]

        self.assertEqual(normalize_change_uids(rows), [])

    def test_normalize_change_uids_skips_non_mapping_rows(self):
        rows = [None, 123, {"feature_uid": "uid:x"}, {"feature_uid": "uid:y"}]

        self.assertEqual(normalize_change_uids(rows), ["uid:x", "uid:y"])


if __name__ == "__main__":
    unittest.main()
