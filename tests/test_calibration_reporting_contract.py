import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from feng_shui_gis.calibration_reporting import (
    build_calibration_popup_html,
    write_calibration_report_files,
)


class CalibrationReportingContractTests(unittest.TestCase):
    def test_build_calibration_popup_html_contains_core_sections(self):
        html = build_calibration_popup_html(
            report={
                "roc_auc": 0.81,
                "pr_auc": 0.74,
                "positive_count": 12,
                "negative_count": 20,
                "valid_count": 8,
                "best_f1": 0.7,
                "best_f1_threshold": 0.61,
                "best_youden_j": 0.55,
                "best_youden_threshold": 0.58,
                "calibration_scope": "local_profile_tuning",
                "tuned_weight_summary": "slope:+0.1",
                "tuned_parameter_summary": "slope_target:+2.0",
                "base_roc_auc": 0.72,
                "base_pr_auc": 0.63,
                "profile_export_status": "saved",
                "exported_profile_key": "general_cal",
                "profile_export_path": "/tmp/profile.json",
                "local_profile_registry_path": "/tmp/local_profiles.json",
                "paper_evidence_summary": "terrain.slope_target=+18.00(A)",
                "paper_evidence_records": [
                    {"source_doi": ["10.1234/example"]},
                ],
            },
            json_path="/tmp/calibration.json",
            md_path="/tmp/calibration.md",
            text_lang="en",
            metric_compare_html="<table><tr><td>metric</td></tr></table>",
            metadata_html="<div>metadata</div>",
            history_html="<div>history</div>",
        )
        self.assertIn("Calibration Result", html)
        self.assertIn("Metric comparison", html)
        self.assertIn("/tmp/calibration.json", html)
        self.assertIn("10.1234/example", html)

    def test_write_calibration_report_files_writes_json_and_markdown_sections(self):
        report = {
            "culture_key": "east_asia",
            "period_key": "joseon",
            "profile_key": "general",
            "hemisphere": "north",
            "negative_ratio": 3,
            "random_seed": 17,
            "positive_count": 12,
            "negative_count": 20,
            "valid_count": 8,
            "roc_auc": 0.81,
            "pr_auc": 0.74,
            "best_f1": 0.7,
            "best_f1_threshold": 0.61,
            "best_youden_j": 0.55,
            "best_youden_threshold": 0.58,
            "calibration_validation_enabled": True,
            "calibration_split_mode": "deterministic_holdout",
            "calibration_split_reason": "separate evaluation rows retained",
            "calibration_scope": "local_profile_tuning",
            "tuned_weight_summary": "slope:+0.1",
            "tuned_parameter_summary": "slope_target:+2.0",
            "base_roc_auc": 0.72,
            "base_pr_auc": 0.63,
            "profile_export_status": "saved",
            "exported_profile_key": "general_cal",
            "profile_export_path": "/tmp/profile.json",
            "local_profile_registry_path": "/tmp/local_profiles.json",
            "paper_evidence_summary": "terrain.slope_target=+18.00(A)",
            "paper_evidence_records": [{"source_doi": ["10.1234/example"]}],
            "site_metadata_summary": {
                "layer_name": "Sites",
                "groupings": [],
            },
        }
        with TemporaryDirectory() as tmpdir:
            paths = write_calibration_report_files(
                report=report,
                report_dir=tmpdir,
                stamp="20260401_120000",
                text_lang="en",
            )
            self.assertTrue(Path(paths["json_path"]).exists())
            self.assertTrue(Path(paths["md_path"]).exists())
            markdown = Path(paths["md_path"]).read_text(encoding="utf-8")
            self.assertIn("Metric comparison", markdown)
            self.assertIn("Calibration history comparison", markdown)
            self.assertIn("Paper evidence", markdown)


if __name__ == "__main__":
    unittest.main()
