import unittest

from qgis.PyQt.QtWidgets import QApplication, QFrame, QProgressBar, QVBoxLayout

from feng_shui_gis.dock_widget_guide_sections import (
    build_analytical_section,
    build_audit_section,
    build_interpretation_section,
)


# These build real widgets and assert on objectName()/count(), so the shared
# qgis stub cannot stand in for them; skip unless a genuine PyQt is importable.
HAS_QT = hasattr(QApplication, "instance")


@unittest.skipUnless(HAS_QT, "PyQt runtime required to build guide-section widgets")
class DockWidgetGuideSectionsContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication([])

    def test_interpretation_section_binds_summary_intro_steps_and_progress(self):
        card = QFrame()
        layout = QVBoxLayout(card)
        progress = QProgressBar(card)
        refs = build_interpretation_section(card, layout, progress)
        self.assertIs(refs.workflow_progress_label, progress)
        self.assertEqual(refs.progress_summary_label.objectName(), "guideSummary")
        self.assertEqual(refs.next_step_label.objectName(), "guideNext")

    def test_analytical_section_provides_metric_and_evidence_widgets(self):
        card = QFrame()
        layout = QVBoxLayout(card)
        refs = build_analytical_section(card, layout, lambda *_args: None)
        self.assertGreater(refs.metric_help_combo.count(), 0)
        self.assertEqual(refs.metric_help_hint.objectName(), "metricHint")
        self.assertEqual(refs.evidence_widget.objectName(), "guideWidget")

    def test_audit_section_provides_diagnostics_and_status_widgets(self):
        card = QFrame()
        layout = QVBoxLayout(card)
        refs = build_audit_section(card, layout)
        self.assertEqual(refs.dem_diag_widget.objectName(), "guideWidget")
        self.assertEqual(refs.workflow_status_label.objectName(), "guideStatus")


if __name__ == "__main__":
    unittest.main()
