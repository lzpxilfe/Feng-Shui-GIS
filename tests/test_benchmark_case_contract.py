import json
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class BenchmarkCaseContractTests(unittest.TestCase):
    def test_case_001_and_validation_docs_lock_descriptive_cluster_level_language(self):
        case_text = (ROOT / "benchmarks" / "case_001_korea_tomb.md").read_text(
            encoding="utf-8"
        ).lower()
        validation_text = (ROOT / "docs" / "validation_protocol.md").read_text(
            encoding="utf-8"
        ).lower()
        operations_text = (ROOT / "docs" / "operations_playbook.md").read_text(
            encoding="utf-8"
        ).lower()
        benchmark_plan_text = (ROOT / "docs" / "benchmark_plan.md").read_text(
            encoding="utf-8"
        ).lower()

        self.assertIn("descriptive_benchmark", case_text)
        self.assertIn("cluster-level", case_text)
        self.assertIn("polygon centroid", case_text)
        self.assertIn("auto-hydro only", case_text)
        self.assertIn("context_vs_neutral", case_text)
        self.assertIn("calibrated_vs_context", case_text)
        self.assertIn("false positives", case_text)
        self.assertIn("false negatives", case_text)

        self.assertIn("descriptive benchmark", validation_text)
        self.assertIn("centroid proxies", validation_text)
        self.assertIn("auto-hydro", validation_text)
        self.assertIn("--case-dir", operations_text)
        self.assertIn("context_vs_neutral", operations_text)
        self.assertIn("calibrated_vs_context", operations_text)
        self.assertIn("canonical real-data case", benchmark_plan_text)

    def test_build_benchmark_manifest_cli_can_read_case_dir_contract(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            case_dir = Path(temp_dir) / "gongju_baekje_case"
            case_dir.mkdir(parents=True, exist_ok=True)
            case_payload = {
                "case_id": "gongju_baekje_case",
                "title": "Gongju Baekje study",
                "workflow": ["analysis", "compare", "calibration"],
                "score_drift_tolerance": 0.05,
                "benchmark": {
                    "mode": "descriptive_benchmark",
                    "truth_level": "cluster_level",
                    "water_policy": "auto_hydro_only",
                    "compare_pairs": [
                        {"id": "context_vs_neutral", "base": "neutral", "candidate": "context"},
                        {"id": "calibrated_vs_context", "base": "context", "candidate": "calibrated"},
                    ],
                },
                "expected": {
                    "required_artifacts": {
                        "run_manifest": "reports/run_manifest.json",
                        "benchmark_manifest": "reports/benchmark_manifest.json",
                    }
                },
            }
            (case_dir / "case.json").write_text(
                json.dumps(case_payload, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )

            output = subprocess.run(
                [
                    "python3",
                    str(ROOT / "tools" / "build_benchmark_manifest.py"),
                    "--case-dir",
                    str(case_dir),
                    "--service",
                    "analysis",
                    "--benchmark-tier",
                    "small",
                    "--qgis-version",
                    "3.40.5",
                    "--runtime-seconds",
                    "12.0",
                    "--peak-memory-mb",
                    "512",
                ],
                cwd=ROOT,
                check=True,
                capture_output=True,
                text=True,
            )
            manifest = json.loads(output.stdout)

            self.assertEqual(manifest["dataset"]["id"], "gongju_baekje_case")
            self.assertEqual(manifest["workflow_steps"], ["analysis", "compare", "calibration"])
            self.assertEqual(manifest["score_drift_tolerance"], 0.05)
            self.assertEqual(manifest["case"]["truth_level"], "cluster_level")
            self.assertEqual(manifest["case"]["water_policy"], "auto_hydro_only")
            self.assertIn("required_artifacts", manifest["expected_contract"])


if __name__ == "__main__":
    unittest.main()
