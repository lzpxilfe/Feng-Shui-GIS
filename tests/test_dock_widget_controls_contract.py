import unittest

from feng_shui_gis.dock_widget_controls import (
    advanced_context_control_state,
    mountain_control_state,
)


class DockWidgetControlsContractTests(unittest.TestCase):
    def test_advanced_context_control_state_mirrors_enabled_flag(self):
        enabled = advanced_context_control_state(True)
        disabled = advanced_context_control_state(False)
        self.assertTrue(enabled["culture_combo_enabled"])
        self.assertTrue(enabled["show_experimental_contexts_enabled"])
        self.assertFalse(disabled["period_combo_enabled"])
        self.assertFalse(disabled["context_param_combo_enabled"])

    def test_mountain_control_state_mirrors_enabled_flag(self):
        enabled = mountain_control_state(True)
        disabled = mountain_control_state(False)
        self.assertTrue(enabled["language_enabled"])
        self.assertTrue(enabled["radius_enabled"])
        self.assertFalse(disabled["limit_enabled"])


if __name__ == "__main__":
    unittest.main()
