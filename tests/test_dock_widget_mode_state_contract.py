import unittest

from feng_shui_gis.dock_widget_mode_state import (
    advanced_options_panel_state,
    usage_goal_guidance_state,
    usage_goal_preset_state,
)


class DockWidgetModeStateContractTests(unittest.TestCase):
    def test_advanced_options_panel_state_tracks_expanded_shape(self):
        expanded = advanced_options_panel_state(True)
        collapsed = advanced_options_panel_state(False)
        self.assertTrue(expanded["panel_visible"])
        self.assertEqual(expanded["arrow"], "down")
        self.assertFalse(collapsed["button_checked"])
        self.assertEqual(collapsed["arrow"], "right")

    def test_usage_goal_preset_state_forces_analysis_tab_for_preset_profiles(self):
        state = usage_goal_preset_state("tomb", profile_key="ridge_tomb", include_terms=True)
        self.assertEqual(state["profile_key"], "ridge_tomb")
        self.assertTrue(state["include_terms"])
        self.assertTrue(state["force_analysis_tab"])
        self.assertFalse(state["expand_advanced"])

        custom = usage_goal_preset_state("custom", profile_key=None, include_terms=False)
        self.assertTrue(custom["expand_advanced"])
        self.assertFalse(custom["force_analysis_tab"])

    def test_usage_goal_guidance_state_formats_goal_and_profile_labels(self):
        guidance = usage_goal_guidance_state(
            "custom",
            goal_label="Custom",
            profile_label_text="Manual <Preset>",
            custom_hint_template="<b>Custom</b> uses {profile}",
            default_hint_template="<b>{goal}</b> uses {profile}",
            guide_intro_html="Intro",
            guide_steps_html="Steps",
        )
        self.assertIn("Manual &lt;Preset&gt;", guidance["goal_hint_html"])
        self.assertEqual(guidance["guide_intro_html"], "Intro")
        self.assertEqual(guidance["guide_steps_html"], "Steps")


if __name__ == "__main__":
    unittest.main()
