import json
import pathlib
import tempfile
import unittest

from feng_shui_gis.compare_reporting import (
    build_compare_popup_html,
    build_compare_report_payload,
    write_compare_report,
)


class CompareReportingContractTests(unittest.TestCase):
    def test_build_compare_report_payload_preserves_core_fields(self):
        payload = build_compare_report_payload(
            stamp="20260401_210000",
            site_layer_name="sites",
            base_profile_key="general",
            compare_profile_key="general_korea_early_modern_cal_20260401",
            base_stats={"mean": 0.51},
            compare_stats={"mean": 0.61},
            delta_stats={"mean_delta": 0.10},
            top_changes=[{"label": "A"}],
            change_layer_name="sites_compare",
        )
        self.assertEqual(payload["timestamp"], "20260401_210000")
        self.assertEqual(payload["site_layer_name"], "sites")
        self.assertEqual(payload["compare_profile_key"], "general_korea_early_modern_cal_20260401")
        self.assertEqual(payload["top_changes"][0]["label"], "A")

    def test_write_compare_report_writes_json_and_markdown(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            payload, json_path, md_path = write_compare_report(
                report_dir=tmpdir,
                label_language="en",
                site_layer_name="sites",
                base_profile_key="general",
                compare_profile_key="general_cal",
                base_stats={"mean": 0.4},
                compare_stats={"mean": 0.6},
                delta_stats={"mean_delta": 0.2, "max_gain": 0.3, "max_drop": -0.1},
                top_changes=[
                    {
                        "label": "Feature 1",
                        "base_score": 0.2,
                        "compare_score": 0.9,
                        "delta": 0.7,
                        "base_reason": "ridge weak",
                        "compare_reason": "ridge strong",
                    }
                ],
                change_layer_name="sites_compare",
            )
            self.assertTrue(pathlib.Path(json_path).is_file())
            self.assertTrue(pathlib.Path(md_path).is_file())
            self.assertEqual(payload["change_layer_name"], "sites_compare")
            report_json = json.loads(pathlib.Path(json_path).read_text(encoding="utf-8"))
            markdown = pathlib.Path(md_path).read_text(encoding="utf-8")
            self.assertEqual(report_json["site_layer_name"], "sites")
            self.assertIn("Feature 1", markdown)
            self.assertIn("Top changed features", markdown)

    def test_compare_popup_html_mentions_layers_and_reports(self):
        html = build_compare_popup_html(
            label_language="en",
            base_profile_key="general",
            compare_profile_key="general_cal",
            base_stats={"count": 2, "mean": 0.4, "min": 0.2, "max": 0.7},
            compare_stats={"count": 2, "mean": 0.6, "min": 0.4, "max": 0.9},
            delta_stats={"mean_delta": 0.2, "max_gain": 0.5, "max_drop": -0.1},
            top_changes=[
                {
                    "label": "Feature 1",
                    "base_score": 0.2,
                    "compare_score": 0.9,
                    "delta": 0.7,
                    "base_reason": "weak",
                    "compare_reason": "strong",
                }
            ],
            selected_change_count=1,
            zoom_applied=True,
            change_layer_name="sites_compare",
            json_path="/tmp/report.json",
            md_path="/tmp/report.md",
            base_layer_name="base_layer",
            compare_layer_name="compare_layer",
        )
        self.assertIn("base_layer", html)
        self.assertIn("compare_layer", html)
        self.assertIn("Feature 1", html)
        self.assertIn("/tmp/report.json", html)


if __name__ == "__main__":
    unittest.main()
