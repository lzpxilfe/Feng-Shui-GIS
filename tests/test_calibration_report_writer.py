import unittest

from feng_shui_gis.reporting.calibration_report_writer import CalibrationReportWriter


class CalibrationReportWriterTests(unittest.TestCase):
    def test_build_markdown_includes_goal_phase_and_report_sections(self):
        report = {
            "positive_count": 8,
            "negative_count": 24,
            "culture_key": "korea",
            "period_key": "early_modern",
            "profile_key": "tomb",
            "hemisphere": "north",
            "negative_ratio": 3,
            "random_seed": 42,
            "calibration_scope": "local_profile_tuning",
            "tuned_weight_summary": "ridge:+0.150",
            "tuned_parameter_summary": "slope_target:+1.000",
            "profile_export_status": "exported",
            "exported_profile_key": "tomb_korea_early_modern_cal_20260401",
            "profile_export_path": "/tmp/profile.json",
            "local_profile_registry_path": "/tmp/local_profiles.json",
            "reported_metric_phase": "held_out_evaluation",
            "reported_metrics": {
                "count": 6,
                "roc_auc": 0.82,
                "pr_auc": 0.77,
                "best_f1": 0.74,
                "best_f1_threshold": 0.51,
                "best_youden_j": 0.63,
                "best_youden_threshold": 0.62,
            },
            "reported_baseline_metrics": {
                "count": 6,
                "roc_auc": 0.68,
                "pr_auc": 0.60,
                "best_f1": 0.58,
                "best_f1_threshold": 0.49,
                "best_youden_j": 0.44,
                "best_youden_threshold": 0.55,
            },
        }

        markdown = CalibrationReportWriter.build_markdown(
            report=report,
            stamp="20260401_120000",
            text_lang="en",
            metric_compare_markdown="metric block",
            metadata_markdown="metadata block",
            history_markdown="history block",
            paper_evidence_summary="paper summary",
            paper_evidence_references="doi:10.1234/example",
        )

        self.assertIn("Feng Shui Calibration Report (20260401_120000)", markdown)
        self.assertIn("## Interpretation", markdown)
        self.assertIn("## Analytical", markdown)
        self.assertIn("## Audit", markdown)
        self.assertIn("Held-out evaluation", markdown)
        self.assertIn("Local tuning of profile weights and parameters", markdown)
        self.assertIn("metric block", markdown)
        self.assertIn("metadata block", markdown)
        self.assertIn("history block", markdown)
        self.assertIn("doi:10.1234/example", markdown)

    def test_build_popup_html_includes_layered_sections(self):
        report = {
            "positive_count": 8,
            "negative_count": 24,
            "culture_key": "korea",
            "period_key": "early_modern",
            "profile_key": "tomb",
            "hemisphere": "north",
            "negative_ratio": 3,
            "random_seed": 42,
            "calibration_scope": "local_profile_tuning",
            "tuned_weight_summary": "ridge:+0.150",
            "tuned_parameter_summary": "slope_target:+1.000",
            "profile_export_status": "exported",
            "exported_profile_key": "tomb_korea_early_modern_cal_20260401",
            "profile_export_path": "/tmp/profile.json",
            "local_profile_registry_path": "/tmp/local_profiles.json",
            "reported_metric_phase": "held_out_evaluation",
            "reported_metrics": {
                "count": 6,
                "roc_auc": 0.82,
                "pr_auc": 0.77,
                "best_f1": 0.74,
                "best_f1_threshold": 0.51,
                "best_youden_j": 0.63,
                "best_youden_threshold": 0.62,
            },
            "reported_baseline_metrics": {
                "count": 6,
                "roc_auc": 0.68,
                "pr_auc": 0.60,
            },
            "calibration_split": {
                "deterministic_split": True,
                "fit_count": 18,
                "selection_count": 8,
                "report_count": 6,
            },
        }

        html = CalibrationReportWriter.build_popup_html(
            report=report,
            text_lang="en",
            json_path="/tmp/calibration.json",
            md_path="/tmp/calibration.md",
            metric_compare_html="<p>metric html</p>",
            metadata_html="<p>metadata html</p>",
            history_html="<p>history html</p>",
            paper_evidence_summary="paper summary",
            paper_evidence_references="doi:10.1234/example",
        )

        self.assertIn("Interpretation", html)
        self.assertIn("Analytical", html)
        self.assertIn("Audit", html)
        self.assertIn("Split contract", html)
        self.assertIn("/tmp/calibration.json", html)


if __name__ == "__main__":
    unittest.main()
