import json
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class UserFlowSmokeTests(unittest.TestCase):
    def test_smoke_payload_contains_asset_and_headless_contract(self):
        asset_payload = json.loads(
            subprocess.run(
                ["python3", str(ROOT / "tools" / "run_asset_smoke.py")],
                cwd=ROOT,
                check=True,
                capture_output=True,
                text=True,
            ).stdout
        )
        headless_payload = json.loads(
            subprocess.run(
                ["python3", str(ROOT / "tools" / "run_headless_smoke.py"), "--dry-run"],
                cwd=ROOT,
                check=True,
                capture_output=True,
                text=True,
            ).stdout
        )

        self.assertTrue(asset_payload["ok"])
        self.assertIn("workflow_steps", asset_payload)
        self.assertIn("analysis", asset_payload["workflow_steps"])
        self.assertIn("fixture_case_ids", headless_payload)
        self.assertEqual(headless_payload["status"], "dry_run_contract_ready")
        self.assertEqual(asset_payload.get("fixture_count"), len(asset_payload.get("fixture_cases", [])))
        self.assertEqual(len(asset_payload["fixture_cases"]), 3)

    def test_first_run_docs_exist_and_reference_sample_project(self):
        readme = (ROOT / "docs" / "first_run_guide.md").read_text(encoding="utf-8")
        sample_readme = (ROOT / "examples" / "sample_project" / "README.md").read_text(
            encoding="utf-8"
        )

        self.assertIn("1.", readme)
        self.assertIn("tools/setup_study_case.py", readme)
        self.assertIn("sample_project", sample_readme)


if __name__ == "__main__":
    unittest.main()
