import unittest

from feng_shui_gis.dock_widget_workflow import workflow_checks_state


class DockWidgetWorkflowContractTests(unittest.TestCase):
    def test_analysis_mode_requires_sites_and_hydro_readiness(self):
        mode_name, action_name, checks = workflow_checks_state(
            mode_tab_index=1,
            goal_key="general",
            dem_ready=True,
            sites_ready=False,
            water_ready=False,
            analysis_auto_hydro=True,
            landscape_auto_hydro=False,
            include_terms=False,
        )
        self.assertTrue(mode_name)
        self.assertTrue(action_name)
        self.assertEqual(checks[1][1], False)
        self.assertEqual(checks[2][1], True)

    def test_landscape_mode_uses_terms_guidance_for_shape_goals(self):
        mode_name, action_name, checks = workflow_checks_state(
            mode_tab_index=0,
            goal_key="tomb",
            dem_ready=True,
            sites_ready=False,
            water_ready=True,
            analysis_auto_hydro=False,
            landscape_auto_hydro=False,
            include_terms=False,
        )
        self.assertTrue(mode_name)
        self.assertTrue(action_name)
        self.assertIn("term", checks[2][0].lower())
        self.assertFalse(checks[2][1])


if __name__ == "__main__":
    unittest.main()
