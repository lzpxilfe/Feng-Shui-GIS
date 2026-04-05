import unittest

from feng_shui_gis.compare_layer_actions import (
    select_changed_features,
    zoom_to_selected_features,
)


class _DummyFields:
    def names(self):
        return ["feature_uid"]


class _DummyLayer:
    def __init__(self, name):
        self._name = name
        self._selected = []
        self.cleared = 0

    def name(self):
        return self._name

    def fields(self):
        return _DummyFields()

    def removeSelection(self):
        self.cleared += 1
        self._selected = []

    def selectByIds(self, ids):
        self._selected = list(ids)

    def selectedFeatureIds(self):
        return list(self._selected)


class CompareLayerActionsContractTests(unittest.TestCase):
    def test_select_changed_features_applies_selection_and_activates_compare_layer(self):
        base = _DummyLayer("base")
        compare = _DummyLayer("compare")
        logs = []
        activated = []

        def _uid_match_summary(layer, feature_uids, field_names=None):
            return {
                "feature_ids": [10, 20],
                "ambiguous": [],
                "missing": [],
            }

        selected = select_changed_features(
            base_layer=base,
            compare_layer=compare,
            feature_uids=["u1", "u2"],
            uid_match_summary=_uid_match_summary,
            log_debug=logs.append,
            set_active_layer=activated.append,
        )
        self.assertEqual(selected, 2)
        self.assertEqual(base.selectedFeatureIds(), [10, 20])
        self.assertEqual(compare.selectedFeatureIds(), [10, 20])
        self.assertEqual(activated, [compare])

    def test_select_changed_features_fails_closed_when_match_count_mismatches(self):
        layer = _DummyLayer("compare")
        logs = []

        def _uid_match_summary(layer, feature_uids, field_names=None):
            return {
                "feature_ids": [10],
                "ambiguous": [],
                "missing": [],
            }

        selected = select_changed_features(
            base_layer=None,
            compare_layer=layer,
            feature_uids=["u1", "u2"],
            uid_match_summary=_uid_match_summary,
            log_debug=logs.append,
            set_active_layer=lambda layer: None,
        )
        self.assertEqual(selected, 0)
        self.assertTrue(any("expected 2, selected 1" in log for log in logs))

    def test_zoom_to_selected_features_uses_callback_only_when_selection_exists(self):
        layer = _DummyLayer("compare")
        layer.selectByIds([1, 2])
        zoomed = []

        self.assertTrue(
            zoom_to_selected_features(
                layer=layer,
                zoom_callback=zoomed.append,
                log_debug=lambda _message: None,
            )
        )
        self.assertEqual(zoomed, [layer])

        empty = _DummyLayer("empty")
        self.assertFalse(
            zoom_to_selected_features(
                layer=empty,
                zoom_callback=zoomed.append,
                log_debug=lambda _message: None,
            )
        )


if __name__ == "__main__":
    unittest.main()
