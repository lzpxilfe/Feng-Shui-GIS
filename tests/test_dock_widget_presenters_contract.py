import unittest

from feng_shui_gis.dock_widget_presenters import (
    apply_workflow_presentation,
    build_evidence_summary_html,
    metric_help_text,
    quick_number_html,
    workflow_recent_status_text,
)


class _DummyLabel:
    def __init__(self):
        self.value = None

    def setText(self, text):
        self.value = text


class _DummyProgress:
    def __init__(self):
        self.value = None

    def setValue(self, value):
        self.value = value


class _DummyRefs:
    def __init__(self):
        self.workflow_progress = _DummyProgress()
        self.progress_summary_label = _DummyLabel()
        self.next_step_label = _DummyLabel()
        self.checklist_label = _DummyLabel()
        self.workflow_status_label = _DummyLabel()


class DockWidgetPresentersContractTests(unittest.TestCase):
    def test_apply_workflow_presentation_updates_bound_widgets(self):
        refs = _DummyRefs()
        apply_workflow_presentation(
            refs,
            {
                "percent": 75,
                "summary_text": "Research flow ready",
                "next_step_text": "Run analysis",
                "checklist_html": "<ul><li>done</li></ul>",
                "recent_status_text": "Recent status: waiting",
            },
        )
        self.assertEqual(refs.workflow_progress.value, 75)
        self.assertEqual(refs.progress_summary_label.value, "Research flow ready")
        self.assertIn("Run analysis", refs.next_step_label.value)

    def test_build_evidence_summary_html_marks_exploratory_context(self):
        html = build_evidence_summary_html(
            records=[{"evidence_level": "A"}, {"evidence_level": "U"}],
            advanced_context_enabled=True,
            culture_key="ryukyu",
        )
        self.assertIn("Evidence", html)
        self.assertIn("Exploratory", html)

    def test_workflow_recent_status_text_formats_status_line(self):
        text = workflow_recent_status_text("calibration running")
        self.assertIn("calibration running", text)

    def test_metric_help_text_and_quick_number_html_have_safe_fallbacks(self):
        self.assertIn("No description", metric_help_text(None))
        self.assertIn("Quick Number Read", quick_number_html())


if __name__ == "__main__":
    unittest.main()
