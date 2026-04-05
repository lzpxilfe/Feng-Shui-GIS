import unittest

from feng_shui_gis.mountain_enrichment import (
    group_layers_by_crs,
    resolve_mountain_name_options,
)


class _DummyCrs:
    def __init__(self, authid):
        self._authid = authid

    def authid(self):
        return self._authid

    def isValid(self):
        return bool(self._authid)


class _DummyLayer:
    def __init__(self, name, authid, valid=True):
        self._name = name
        self._authid = authid
        self._valid = valid

    def name(self):
        return self._name

    def crs(self):
        return _DummyCrs(self._authid)


class MountainEnrichmentContractTests(unittest.TestCase):
    def test_resolve_mountain_name_options_clamps_values(self):
        result = resolve_mountain_name_options(
            {
                "enabled_default": True,
                "radius_default_m": 5000,
                "radius_min_m": 1000,
                "radius_max_m": 10000,
                "max_features_default": 3,
                "max_features_min": 1,
                "max_features_max": 8,
                "language_default": "local",
            },
            enabled=False,
            radius_m=50000,
            max_features=99,
            preferred_language="bad",
        )
        self.assertEqual(result, (False, 10000, 8, "local"))

    def test_group_layers_by_crs_groups_valid_layers_only(self):
        layers = [
            _DummyLayer("a", "EPSG:5186"),
            _DummyLayer("b", "EPSG:5186"),
            _DummyLayer("c", "EPSG:4326"),
        ]
        groups = group_layers_by_crs(
            layers,
            is_valid_layer=lambda layer: layer.name() != "b",
            crs_key_for_layer=lambda layer: (layer.crs().authid(), layer.crs()),
        )
        self.assertEqual(len(groups), 2)
        self.assertEqual(groups[0]["layers"][0].name(), "a")


if __name__ == "__main__":
    unittest.main()
