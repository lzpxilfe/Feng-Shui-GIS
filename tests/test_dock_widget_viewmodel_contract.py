import unittest

from feng_shui_gis.dock_widget_viewmodel import (
    context_evidence_state,
    dem_diagnostics_state,
    evidence_summary_state,
    recommendation_state,
    workflow_presentation_state,
)


class DockWidgetViewModelContractTests(unittest.TestCase):
    def test_recommendation_state_exposes_compare_pair(self):
        state = recommendation_state(
            "general",
            "korea",
            "early_modern",
            ["general", "general_korea_early_modern_cal_20260401"],
        )
        self.assertTrue(state["can_apply_recommended"])
        self.assertEqual(state["comparison_base_key"], "general")

    def test_workflow_presentation_state_builds_summary_and_next_step(self):
        state = workflow_presentation_state(
            mode_name="Analysis",
            action_name="Run",
            checks=[("Select DEM", True), ("Select sites", False)],
            goal_name="Settlement",
            profile_name="general",
            label_language="en",
            advanced_context_enabled=True,
            mountain_enabled=True,
            mountain_language="ko",
            status_text="waiting",
        )
        self.assertEqual(state["percent"], 50)
        self.assertIn("Settlement", state["summary_text"])
        self.assertIn("Select sites", state["next_step_text"])
        self.assertIn("Pending", state["checklist_html"])

    def test_evidence_summary_state_marks_experimental_context(self):
        state = evidence_summary_state(
            records=[
                {"evidence_level": "A"},
                {"evidence_level": "C"},
                {"evidence_level": "U"},
            ],
            advanced_context_enabled=True,
            culture_key="ryukyu",
        )
        self.assertIn("Exploratory", state["quality"])
        self.assertIn("Evidence Summary", state["html"])

    def test_dem_diagnostics_state_formats_projected_and_error_cases(self):
        ready = dem_diagnostics_state(
            layer_name="dem",
            diagnostics={
                "dem_step": 10.0,
                "width": 200.0,
                "height": 100.0,
                "spacing": 32.0,
                "approx_nodes": 120,
            },
            crs_is_geographic=False,
        )
        error_state = dem_diagnostics_state(error_text="bad raster")
        self.assertIn("dem", ready["html"])
        self.assertIn("projected", ready["html"])
        self.assertIn("bad raster", error_state["html"])

    def test_context_evidence_state_supports_general_and_exploratory_modes(self):
        general = context_evidence_state(
            advanced_context_enabled=False,
            culture_key="korea",
            culture_name="Korea",
            period_name="Joseon",
            ui_language="en",
            records=[],
            selected_index=0,
        )
        self.assertEqual(general["combo_items"], [])
        self.assertIn("General principles mode", general["hint_text"])

        exploratory = context_evidence_state(
            advanced_context_enabled=True,
            culture_key="ryukyu",
            culture_name="Ryukyu",
            period_name="Early Modern",
            ui_language="en",
            records=[
                {
                    "group": "weight_bias",
                    "name": "water",
                    "value": 0.12,
                    "evidence_level": "C",
                    "source_doi": ["10.1234/example"],
                    "note": "heuristic prior",
                }
            ],
            selected_index=0,
        )
        self.assertEqual(exploratory["selected_index"], 0)
        self.assertIn("Exploratory", exploratory["hint_text"])
        self.assertIn("weight_bias.water", exploratory["param_hint_text"])


if __name__ == "__main__":
    unittest.main()
