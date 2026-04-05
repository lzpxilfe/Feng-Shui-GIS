import unittest
from unittest.mock import patch

from feng_shui_gis.compare_service_helpers import prepare_compare_results


class _FakeLayer:
    def __init__(self, name):
        self._name = name

    def name(self):
        return self._name


class _FakePlugin:
    def __init__(self):
        self.styled = []
        self.configured = []

    def _score_stats(self, layer):
        return {"count": 2, "mean": 0.5 if layer.name() == "base" else 0.7}

    def _pairwise_score_delta(self, base_layer, compare_layer):
        return {"mean_delta": 0.2, "max_gain": 0.3, "max_drop": -0.1}

    def _top_score_changes(self, base_layer, compare_layer):
        return [{"feature_uid": "u1", "delta": 0.2}]

    def _sanitize_top_change_rows(self, rows):
        return list(rows)

    def _validate_compare_feature_contract(self, base_layer, compare_layer, top_changes):
        return True, ""

    def _select_top_changed_features(self, base_layer, compare_layer, top_changes):
        return len(top_changes)

    def _zoom_to_selected_features(self, compare_layer):
        return True

    def _export_top_changed_features_layer(
        self,
        compare_layer,
        top_changes,
        compare_profile_key,
        label_language,
    ):
        return _FakeLayer("changes")

    def _style_compare_change_layer(self, layer, label_language):
        self.styled.append((layer.name(), label_language))

    def _configure_layer_click_info(self, layer, label_language):
        self.configured.append((layer.name(), label_language))


class CompareServiceHelpersContractTests(unittest.TestCase):
    @patch("feng_shui_gis.compare_service_helpers.QgsProject")
    def test_prepare_compare_results_returns_contract_payload(self, project_cls):
        project_cls.instance.return_value.addMapLayer.return_value = None
        plugin = _FakePlugin()
        result = prepare_compare_results(
            plugin=plugin,
            base_layer=_FakeLayer("base"),
            compare_layer=_FakeLayer("compare"),
            compare_profile_key="general_cal",
            label_language="en",
        )
        self.assertEqual(result["change_layer_name"], "changes")
        self.assertEqual(result["selected_change_count"], 1)
        self.assertTrue(result["zoom_applied"])
        self.assertEqual(plugin.styled, [("changes", "en")])
        self.assertEqual(plugin.configured, [("changes", "en")])


if __name__ == "__main__":
    unittest.main()
