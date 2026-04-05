import json
import pathlib
import subprocess
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
FIXTURE_ROOT = ROOT / "tests" / "fixtures"


class WorkflowRegressionContractTests(unittest.TestCase):
    def test_sample_project_assets_exist(self):
        self.assertTrue((ROOT / "examples" / "sample_project" / "README.md").is_file())
        self.assertTrue((ROOT / "examples" / "sample_project" / "sample_project.qgs").is_file())

    def test_fixture_cases_follow_inputs_expected_layout(self):
        expected_case_ids = {
            "clear_hydro_case",
            "exploratory_context_case",
            "calibration_shift_case",
        }
        found_case_ids = set()
        for case_dir in sorted(path for path in FIXTURE_ROOT.iterdir() if path.is_dir()):
            case = json.loads((case_dir / "case.json").read_text(encoding="utf-8"))
            found_case_ids.add(case["case_id"])
            self.assertTrue((case_dir / "inputs").is_dir())
            self.assertTrue((case_dir / "expected").is_dir())
            self.assertTrue((case_dir / "expected" / "report_contract.json").is_file())
            self.assertTrue((case_dir / "expected" / "run_manifest_contract.json").is_file())
            self.assertTrue((case_dir / "expected" / "benchmark_manifest_contract.json").is_file())
            self.assertEqual(case["benchmark"]["mode"], "descriptive_benchmark")
            self.assertIn("required_artifacts", case["expected"])
            self.assertIn("compare_pairs", case["expected"])
            self.assertEqual(len(case["expected"]["compare_pairs"]), 2)
            self.assertIn("truth_level", case["benchmark"])
            self.assertGreater(case["score_drift_tolerance"], 0.0)
        self.assertEqual(found_case_ids, expected_case_ids)

    def test_asset_smoke_outputs_fixture_summary(self):
        output = subprocess.run(
            ["python3", str(ROOT / "tools" / "run_asset_smoke.py")],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        payload = json.loads(output.stdout)
        self.assertTrue(payload["ok"])
        self.assertEqual(len(payload["fixture_cases"]), 3)
        self.assertIn("analysis", payload["workflow_steps"])

    def test_headless_smoke_dry_run_exposes_workflow_contract(self):
        output = subprocess.run(
            ["python3", str(ROOT / "tools" / "run_headless_smoke.py"), "--dry-run"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        payload = json.loads(output.stdout)
        self.assertTrue(payload["ok"])
        self.assertTrue(payload["dry_run"])
        self.assertIn("compare", payload["workflow_steps"])
        self.assertEqual(len(payload["fixture_case_ids"]), 3)


if __name__ == "__main__":
    unittest.main()
