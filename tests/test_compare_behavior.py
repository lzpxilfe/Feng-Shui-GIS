import json
import tempfile
import unittest
import importlib

HAS_QGIS = importlib.util.find_spec("qgis") is not None

if HAS_QGIS:
    from feng_shui_gis.analysis_scoring import explain_top_factors
    from feng_shui_gis.compare_reporting import (
        build_compare_report_payload,
        build_compare_popup_html,
        write_compare_report,
    )
else:  # pragma: no cover - qgis runtime not installed in CI/local env
    explain_top_factors = None
    build_compare_report_payload = None
    build_compare_popup_html = None
    write_compare_report = None


class CompareBehaviorTests(unittest.TestCase):
    @unittest.skipUnless(HAS_QGIS, "QGIS runtime required for compare reporting behavior tests")
    def test_compare_report_payload_roundtrip(self):
        top_changes = [
            {
                "label": "A",
                "base_score": 0.44,
                "compare_score": 0.56,
                "delta": 0.12,
                "base_reason": "ridge dominance",
                "compare_reason": "water proximity improved",
            },
            {
                "label": "B",
                "base_score": 0.82,
                "compare_score": 0.61,
                "delta": -0.21,
                "base_reason": "aspect penalty",
                "compare_reason": "context weight changed",
            },
        ]
        payload = build_compare_report_payload(
            stamp="20260404_120000",
            site_layer_name="sites",
            base_profile_key="general",
            compare_profile_key="region",
            base_stats={"mean": 0.41},
            compare_stats={"mean": 0.45},
            delta_stats={"mean_delta": 0.04, "max_gain": 0.12, "max_drop": -0.21},
            top_changes=top_changes,
            change_layer_name="compare_top_changes",
        )

        self.assertEqual(payload["change_layer_name"], "compare_top_changes")
        self.assertEqual(payload["base_profile_key"], "general")
        self.assertEqual(payload["compare_profile_key"], "region")
        self.assertEqual(len(payload["top_changes"]), 2)
        self.assertGreater(payload["delta_stats"]["max_gain"], payload["delta_stats"]["max_drop"])

    @unittest.skipUnless(HAS_QGIS, "QGIS runtime required for compare reporting behavior tests")
    def test_explain_top_factors_is_deterministic(self):
        indicators = {"slope": 0.7, "aspect": 0.4, "water": 0.9, "tpi": 0.2}
        profile = {"weights": {"slope": 2.0, "water": 3.0, "aspect": 1.0, "tpi": 1.0}}
        text = explain_top_factors(indicators, profile)
        self.assertIn("water", text)
        self.assertIn("slope", text)

    @unittest.skipUnless(HAS_QGIS, "QGIS runtime required for compare reporting behavior tests")
    def test_compare_popup_html_contains_top_change_summary(self):
        html = build_compare_popup_html(
            label_language="en",
            base_profile_key="general",
            compare_profile_key="region",
            base_stats={"count": 6, "mean": 0.4, "min": 0.1, "max": 1.0},
            compare_stats={"count": 6, "mean": 0.6, "min": 0.2, "max": 1.0},
            delta_stats={"mean_delta": 0.2, "max_gain": 0.3, "max_drop": -0.1},
            top_changes=[
                {
                    "label": "A",
                    "base_score": 0.3,
                    "compare_score": 0.6,
                    "delta": 0.3,
                    "base_reason": "A",
                    "compare_reason": "B",
                }
            ],
            selected_change_count=1,
            zoom_applied=True,
            change_layer_name="change_layer",
            json_path="/tmp/change.json",
            md_path="/tmp/change.md",
            base_layer_name="base_layer",
            compare_layer_name="compare_layer",
            reason_excerpt_limit=30,
        )

        self.assertIn("Top changed features", html)
        self.assertIn("Auto-selected", html)
        self.assertIn("change_layer", html)

    @unittest.skipUnless(HAS_QGIS, "QGIS runtime required for compare reporting behavior tests")
    def test_write_compare_report_creates_artifacts(self):
        with tempfile.TemporaryDirectory(prefix="feng-shui-compare-") as report_dir:
            payload, json_path, md_path = write_compare_report(
                report_dir=report_dir,
                label_language="en",
                site_layer_name="sites",
                base_profile_key="general",
                compare_profile_key="region",
                base_stats={"mean": 0.4},
                compare_stats={"mean": 0.5},
                delta_stats={"mean_delta": 0.1, "max_gain": 0.2, "max_drop": -0.2},
                top_changes=[],
                change_layer_name="change_layer",
            )
            payload_obj = json.loads(json_path.read_text(encoding="utf-8"))

            self.assertEqual(payload_obj["site_layer_name"], payload["site_layer_name"])
            self.assertIn("site_layer_name", payload)
            self.assertIn("feng_shui_compare_", json_path.name)
            self.assertTrue((report_dir / md_path).exists() or md_path.startswith("/"))


if __name__ == "__main__":
    unittest.main()
