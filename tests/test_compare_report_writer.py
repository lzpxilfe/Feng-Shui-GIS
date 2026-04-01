import unittest

from feng_shui_gis.reporting.compare_report_writer import CompareReportWriter


class CompareReportWriterTests(unittest.TestCase):
    def test_payload_includes_interpretation_analytical_and_audit_sections(self):
        payload = CompareReportWriter.payload(
            stamp="20260401_120000",
            site_layer_name="Sites",
            base_profile_key="tomb",
            compare_profile_key="tomb_korea_cal",
            base_stats={"mean": 0.4},
            compare_stats={"mean": 0.6},
            delta_stats={"mean_delta": 0.2, "max_gain": 0.3, "max_drop": -0.1},
            top_changes=[
                {
                    "feature_uid": "uid-1",
                    "label": "Site A",
                    "base_score": 0.4,
                    "compare_score": 0.8,
                    "delta": 0.4,
                }
            ],
            change_layer_name="Changes",
            reason_excerpt_limit=32,
        )

        self.assertIn("interpretation", payload)
        self.assertIn("analytical", payload)
        self.assertIn("audit", payload)
        self.assertEqual(payload["audit"]["top_change_feature_uids"], ["uid-1"])

    def test_build_markdown_includes_summary_and_top_changes(self):
        markdown = CompareReportWriter.build_markdown(
            stamp="20260401_120000",
            text_lang="en",
            site_layer_name="Sites",
            base_profile_key="tomb",
            compare_profile_key="tomb_korea_cal",
            base_stats={"mean": 0.4},
            compare_stats={"mean": 0.6},
            delta_stats={"mean_delta": 0.2, "max_gain": 0.3, "max_drop": -0.1},
            top_changes=[
                {
                    "label": "Site A",
                    "base_score": 0.4,
                    "compare_score": 0.8,
                    "delta": 0.4,
                    "base_reason": "base reason text",
                    "compare_reason": "compare reason text",
                }
            ],
            change_layer_name="Changes",
            reason_excerpt_limit=32,
        )

        self.assertIn("Feng Shui Comparison Report (20260401_120000)", markdown)
        self.assertIn("## Interpretation", markdown)
        self.assertIn("## Analytical", markdown)
        self.assertIn("## Audit", markdown)
        self.assertIn("Site A", markdown)
        self.assertIn("Summary statistics", markdown)
        self.assertIn("Top changed features", markdown)

    def test_build_popup_html_includes_export_notes_and_table(self):
        html = CompareReportWriter.build_popup_html(
            text_lang="en",
            base_profile_key="tomb",
            compare_profile_key="tomb_korea_cal",
            base_stats={"count": 4, "mean": 0.4, "min": 0.2, "max": 0.6},
            compare_stats={"count": 4, "mean": 0.6, "min": 0.4, "max": 0.8},
            delta_stats={"mean_delta": 0.2, "max_gain": 0.3, "max_drop": -0.1},
            top_changes=[
                {
                    "label": "Site A",
                    "base_score": 0.4,
                    "compare_score": 0.8,
                    "delta": 0.4,
                    "base_reason": "base reason text",
                    "compare_reason": "compare reason text",
                }
            ],
            selected_change_count=1,
            zoom_applied=True,
            change_layer_name="Changes",
            json_path="/tmp/compare.json",
            md_path="/tmp/compare.md",
            base_layer_name="Base Layer",
            compare_layer_name="Cal Layer",
            reason_excerpt_limit=32,
        )

        self.assertIn("Base Layer", html)
        self.assertIn("Cal Layer", html)
        self.assertIn("Interpretation", html)
        self.assertIn("Analytical", html)
        self.assertIn("Audit", html)
        self.assertIn("Auto-selected", html)
        self.assertIn("Compare JSON", html)
        self.assertIn("Site A", html)


if __name__ == "__main__":
    unittest.main()
