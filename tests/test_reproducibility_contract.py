import json
import pathlib
import subprocess
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
CONFIG_DIR = ROOT / "feng_shui_gis" / "config"


class ReproducibilityContractTests(unittest.TestCase):
    def test_research_docs_and_templates_exist(self):
        required_paths = [
            ROOT / "docs" / "researcher_quickstart.md",
            ROOT / "docs" / "validation_protocol.md",
            ROOT / "docs" / "operations_playbook.md",
            ROOT / "examples" / "README.md",
            ROOT / "examples" / "reproducibility_manifest.template.json",
            ROOT / "examples" / "performance_budget.template.json",
            ROOT / "tools" / "build_repro_manifest.py",
            ROOT / "tools" / "build_benchmark_manifest.py",
        ]
        for path in required_paths:
            self.assertTrue(path.is_file(), f"Missing expected file: {path}")

    def test_manifest_template_covers_all_config_files(self):
        template_path = ROOT / "examples" / "reproducibility_manifest.template.json"
        template = json.loads(template_path.read_text(encoding="utf-8"))
        config_paths = {
            path.relative_to(ROOT).as_posix() for path in sorted(CONFIG_DIR.glob("*.json"))
        }
        template_paths = {row["path"] for row in template["config_snapshot"]}
        self.assertEqual(template_paths, config_paths)
        self.assertIn("dataset", template)
        self.assertIn("plugin", template)
        self.assertIn("repository", template)
        self.assertIn("run", template)
        self.assertIn("artifacts", template)

    def test_context_config_has_base_keys_and_neutral_defaults(self):
        contexts = json.loads((CONFIG_DIR / "contexts.json").read_text(encoding="utf-8"))
        cultures = contexts["cultures"]
        periods = contexts["periods"]
        neutral_defaults = contexts["neutral_defaults"]

        self.assertIn(contexts["base_culture_key"], cultures)
        self.assertIn(contexts["base_period_key"], periods)
        for key in (
            "aspect_targets",
            "aspect_sharpness",
            "water_distance_target",
            "water_distance_sigma",
            "macro_radius_multiplier",
            "micro_radius_multiplier",
            "hyeol_threshold",
            "term_target_shift",
        ):
            self.assertIn(key, neutral_defaults)

    def test_calibration_rules_include_local_sampling_controls(self):
        rules = json.loads((CONFIG_DIR / "analysis_rules.json").read_text(encoding="utf-8"))
        calibration = rules["calibration"]
        for key in (
            "negative_ratio_options",
            "default_negative_ratio",
            "local_bbox_padding_factor",
            "local_bbox_min_padding_cells",
            "trial_multiplier",
        ):
            self.assertIn(key, calibration)

    def test_performance_budget_template_has_service_tiers(self):
        template = json.loads(
            (ROOT / "examples" / "performance_budget.template.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(template["schema_version"], 1)
        budgets = template["budgets"]
        for service_name in ("analysis", "compare", "calibration", "term_extraction"):
            self.assertIn(service_name, budgets)
            for tier in ("small", "medium", "large"):
                self.assertIn(tier, budgets[service_name])
                budget = budgets[service_name][tier]
                self.assertIn("runtime_seconds_max", budget)
                self.assertIn("peak_memory_mb_max", budget)
                self.assertIn("cancel_latency_ms_max", budget)

    def test_manifest_builder_outputs_valid_json(self):
        output = subprocess.run(
            [
                "python3",
                str(ROOT / "tools" / "build_repro_manifest.py"),
                "--dataset-id",
                "smoke-test",
                "--qgis-version",
                "3.40.5",
                "--dem",
                "data/raw/dem.tif",
                "--crs",
                "EPSG:5186",
                "--culture-key",
                "korea",
                "--period-key",
                "early_modern",
                "--include-terms",
            ],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        manifest = json.loads(output.stdout)
        self.assertEqual(manifest["dataset"]["id"], "smoke-test")
        self.assertEqual(manifest["plugin"]["version"], "0.1.2")
        self.assertEqual(manifest["plugin"]["qgis_version"], "3.40.5")
        self.assertEqual(
            {row["path"] for row in manifest["config_snapshot"]},
            {path.relative_to(ROOT).as_posix() for path in sorted(CONFIG_DIR.glob("*.json"))},
        )
        for row in manifest["config_snapshot"]:
            self.assertEqual(len(row["sha256"]), 64)

    def test_benchmark_manifest_builder_outputs_valid_json(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = pathlib.Path(tmpdir)
            run_manifest_path = tmp_root / "run_manifest.json"
            run_manifest_path.write_text(
                json.dumps({"run_id": "abc123", "service_name": "analysis"}),
                encoding="utf-8",
            )
            report_path = tmp_root / "report.json"
            report_path.write_text(
                json.dumps({"reported_metric_phase": "held_out_evaluation"}),
                encoding="utf-8",
            )
            markdown_path = tmp_root / "report.md"
            markdown_path.write_text("# report\n", encoding="utf-8")

            output = subprocess.run(
                [
                    "python3",
                    str(ROOT / "tools" / "build_benchmark_manifest.py"),
                    "--dataset-id",
                    "smoke-test",
                    "--service",
                    "analysis",
                    "--benchmark-tier",
                    "small",
                    "--qgis-version",
                    "3.40.5",
                    "--runtime-seconds",
                    "12.5",
                    "--peak-memory-mb",
                    "384",
                    "--cancel-latency-ms",
                    "700",
                    "--manifest",
                    str(run_manifest_path),
                    "--report",
                    str(report_path),
                    "--markdown",
                    str(markdown_path),
                ],
                cwd=ROOT,
                check=True,
                capture_output=True,
                text=True,
            )
            manifest = json.loads(output.stdout)
            self.assertEqual(manifest["dataset"]["id"], "smoke-test")
            self.assertEqual(manifest["dataset"]["benchmark_tier"], "small")
            self.assertEqual(manifest["service"]["name"], "analysis")
            self.assertEqual(manifest["service"]["runtime_seconds"], 12.5)
            self.assertEqual(manifest["budget"]["tier"], "small")
            self.assertEqual(manifest["budget"]["service"], "analysis")
            self.assertTrue(manifest["artifacts"]["run_manifest"]["exists"])
            self.assertEqual(
                len(manifest["artifacts"]["run_manifest"]["sha256"]),
                64,
            )
            self.assertTrue(manifest["artifacts"]["report_json"]["exists"])
            self.assertTrue(manifest["artifacts"]["report_markdown"]["exists"])


if __name__ == "__main__":
    unittest.main()
