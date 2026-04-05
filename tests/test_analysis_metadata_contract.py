import unittest

from feng_shui_gis.analysis_metadata import (
    metadata_field_name,
    metadata_grouping,
    summarize_site_metadata,
)


class _DummyField:
    def __init__(self, name):
        self._name = name

    def name(self):
        return self._name


class _DummyFeature:
    def __init__(self, values):
        self._values = dict(values)

    def __getitem__(self, key):
        return self._values.get(key)


class _DummyLayer:
    def __init__(self, name, fields, rows):
        self._name = name
        self._fields = [_DummyField(field) for field in fields]
        self._rows = [_DummyFeature(row) for row in rows]

    def name(self):
        return self._name

    def fields(self):
        return self._fields

    def getFeatures(self):
        return iter(self._rows)


class AnalysisMetadataContractTests(unittest.TestCase):
    def test_metadata_field_name_supports_exact_and_partial_matches(self):
        layer = _DummyLayer(
            "sites",
            ["site_class", "country_name", "period_label"],
            [],
        )
        self.assertEqual(metadata_field_name(layer, ("site_class",)), "site_class")
        self.assertEqual(metadata_field_name(layer, ("country",)), "country_name")

    def test_metadata_grouping_and_summary_collect_counts_and_shares(self):
        layer = _DummyLayer(
            "Sites",
            ["site_group", "country", "period"],
            [
                {"site_group": "tomb", "country": "Korea", "period": "Joseon"},
                {"site_group": "tomb", "country": "Korea", "period": "Joseon"},
                {"site_group": "house", "country": "Japan", "period": "Edo"},
            ],
        )
        grouping = metadata_grouping(layer, "site_group", ("site_group",))
        self.assertEqual(grouping["field"], "site_group")
        self.assertEqual(grouping["rows"][0]["value"], "tomb")
        self.assertAlmostEqual(grouping["rows"][0]["share"], 2 / 3)

        summary = summarize_site_metadata(layer)
        self.assertEqual(summary["layer_name"], "Sites")
        self.assertEqual(len(summary["groupings"]), 3)


if __name__ == "__main__":
    unittest.main()
