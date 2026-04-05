import unittest

from feng_shui_gis.dock_widget_state import restore_ui_state, snapshot_ui_state


class _DummyLayerCombo:
    def __init__(self, value=None):
        self.value = value
        self.blocked = False

    def currentLayer(self):
        return self.value

    def setLayer(self, value):
        self.value = value

    def blockSignals(self, flag):
        self.blocked = bool(flag)


class _DummyCombo:
    def __init__(self, values, current=None):
        self.values = list(values)
        self.index = self.values.index(current) if current in self.values else 0
        self.blocked = False

    def currentData(self):
        return self.values[self.index]

    def findData(self, value):
        try:
            return self.values.index(value)
        except ValueError:
            return -1

    def setCurrentIndex(self, index):
        self.index = index

    def blockSignals(self, flag):
        self.blocked = bool(flag)


class _DummyCheck:
    def __init__(self, checked=False):
        self.checked = checked
        self.blocked = False

    def isChecked(self):
        return self.checked

    def setChecked(self, value):
        self.checked = bool(value)

    def blockSignals(self, flag):
        self.blocked = bool(flag)


class _DummySpin:
    def __init__(self, value=0):
        self._value = value
        self.blocked = False

    def value(self):
        return self._value

    def setValue(self, value):
        self._value = value

    def blockSignals(self, flag):
        self.blocked = bool(flag)


class _DummyTabs(_DummySpin):
    def count(self):
        return 3

    def currentIndex(self):
        return self._value

    def setCurrentIndex(self, value):
        self._value = value


class _DummyLabel:
    def __init__(self, text=""):
        self._text = text

    def text(self):
        return self._text

    def setText(self, text):
        self._text = text


class _DummyWidget:
    def __init__(self):
        self.sites_combo = _DummyLayerCombo("sites")
        self.dem_combo = _DummyLayerCombo("dem")
        self.water_combo = _DummyLayerCombo("water")
        self.ui_language_combo = _DummyCombo(["ko", "en"], "ko")
        self.label_language_combo = _DummyCombo(["ko", "en"], "ko")
        self.purpose_combo = _DummyCombo(["settlement", "house"], "settlement")
        self.hemisphere_combo = _DummyCombo(["north", "south"], "north")
        self.web_mountain_checkbox = _DummyCheck(True)
        self.web_mountain_radius_spin = _DummySpin(5000)
        self.web_mountain_limit_spin = _DummySpin(3)
        self.web_mountain_lang_combo = _DummyCombo(["local", "ko", "en"], "ko")
        self.advanced_options_button = _DummyCheck(False)
        self.profile_combo = _DummyCombo(["general", "general_cal"], "general")
        self.advanced_context_checkbox = _DummyCheck(True)
        self.show_experimental_context_checkbox = _DummyCheck(False)
        self.culture_combo = _DummyCombo(["korea", "ryukyu"], "korea")
        self.period_combo = _DummyCombo(["early_modern", "late"], "early_modern")
        self.mode_tabs = _DummyTabs(1)
        self.landscape_auto_hydro_checkbox = _DummyCheck(True)
        self.include_terms_checkbox = _DummyCheck(True)
        self.analysis_auto_hydro_checkbox = _DummyCheck(False)
        self.negative_ratio_combo = _DummyCombo([1, 3, 5], 3)
        self.calibration_seed_spin = _DummySpin(42)
        self.status_label = _DummyLabel("ready")

    def ui_language(self):
        return "ko"

    def label_language(self):
        return "ko"


class DockWidgetStateContractTests(unittest.TestCase):
    def test_snapshot_ui_state_collects_key_inputs(self):
        widget = _DummyWidget()
        state = snapshot_ui_state(widget)
        self.assertEqual(state["sites_layer"], "sites")
        self.assertEqual(state["profile_key"], "general")
        self.assertEqual(state["negative_ratio"], 3)

    def test_restore_ui_state_rehydrates_core_values(self):
        widget = _DummyWidget()
        state = {
            "sites_layer": "sites_2",
            "dem_layer": "dem_2",
            "water_layer": "water_2",
            "ui_language": "en",
            "label_language": "en",
            "purpose_key": "house",
            "hemisphere": "south",
            "web_mountain_enabled": False,
            "web_mountain_radius": 6000,
            "web_mountain_limit": 5,
            "web_mountain_lang": "en",
            "advanced_options_open": True,
            "profile_key": "general_cal",
            "advanced_context_enabled": False,
            "show_experimental_contexts": True,
            "culture_key": "ryukyu",
            "period_key": "late",
            "mode_tab_index": 2,
            "landscape_auto_hydro": False,
            "include_terms": False,
            "analysis_auto_hydro": True,
            "negative_ratio": 5,
            "calibration_seed": 99,
            "status_text": "restored",
        }

        rebuilt = {}

        def _rebuild_culture_combo(value):
            rebuilt["culture"] = value

        restore_ui_state(widget, state, rebuild_culture_combo=_rebuild_culture_combo)
        self.assertEqual(widget.sites_combo.currentLayer(), "sites_2")
        self.assertEqual(widget.profile_combo.currentData(), "general_cal")
        self.assertEqual(widget.calibration_seed_spin.value(), 99)
        self.assertEqual(rebuilt["culture"], "ryukyu")


if __name__ == "__main__":
    unittest.main()
