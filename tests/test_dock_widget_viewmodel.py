import unittest

from feng_shui_gis.dock_widget_viewmodel import DockWidgetProfileViewModel


class DockWidgetViewModelTests(unittest.TestCase):
    def test_recommendation_payload_exposes_compare_actions(self):
        payload = DockWidgetProfileViewModel.recommendation_state_payload(
            current_profile_key="tomb",
            advanced_context_enabled=True,
            culture_key="korea",
            period_key="early_modern",
            available_profile_keys=(
                "tomb",
                "tomb_korea_early_modern_cal_20260331",
            ),
            ui_language="en",
        )

        self.assertTrue(payload["can_apply_recommended"])
        self.assertTrue(payload["can_compare_recommended"])
        self.assertIn("Recommended", payload["guidance_text"])

    def test_workflow_presentation_state_summarizes_pending_step(self):
        state = DockWidgetProfileViewModel.workflow_presentation_state(
            mode_tab_index=1,
            goal_key="tomb",
            dem_ready=True,
            sites_ready=False,
            water_ready=False,
            include_terms_enabled=True,
            analysis_auto_hydro=True,
            landscape_auto_hydro=False,
            ui_language="en",
            label_language="en",
            workflow_mode="quick",
            advanced_context_enabled=False,
            mountain_name_enrichment_enabled=False,
            mountain_language_preference="ko",
            goal_name="Ritual-Burial Landscape",
            profile_name="Tomb",
            recent_status="Waiting for inputs",
        )

        self.assertEqual(state.percent, 50)
        self.assertEqual(len(state.checks), 4)
        self.assertIn("Select candidate point layer", state.next_step_text)
        self.assertIn("Ritual-Burial Landscape", state.summary_text)
        self.assertIn("Quick", state.summary_text)
        self.assertIn("Waiting for inputs", state.status_text)


if __name__ == "__main__":
    unittest.main()
