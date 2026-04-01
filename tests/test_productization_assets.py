import json
import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class ProductizationAssetTests(unittest.TestCase):
    def test_docs_and_sample_project_assets_exist(self):
        required = [
            ROOT / "docs" / "first_run_guide.md",
            ROOT / "docs" / "troubleshooting.md",
            ROOT / "docs" / "bug_report_template.md",
            ROOT / "docs" / "support_bundle_guide.md",
            ROOT / "docs" / "release_checklist.md",
            ROOT / "examples" / "sample_project" / "README.md",
            ROOT / "examples" / "sample_project" / "sample_project.qgz",
            ROOT / "examples" / "sample_project" / "sample_dem.asc",
            ROOT / "examples" / "sample_project" / "sample_water.geojson",
            ROOT / "examples" / "sample_project" / "sample_sites.geojson",
            ROOT / "tools" / "run_headless_smoke.py",
            ROOT / "tools" / "run_asset_smoke.py",
            ROOT / "tools" / "release_guard.py",
        ]
        for path in required:
            self.assertTrue(path.is_file(), f"Missing productization asset: {path}")

    def test_regression_fixture_inventory_exists(self):
        fixture_dir = ROOT / "tests" / "fixtures"
        expected = {
            "clear_hydro_case",
            "exploratory_context_case",
            "calibration_shift_case",
        }
        found = {path.name for path in fixture_dir.iterdir() if path.is_dir()}
        self.assertTrue(expected.issubset(found))
        for case_name in expected:
            case_dir = fixture_dir / case_name
            payload = json.loads((case_dir / "case.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["case_id"], case_name)
            self.assertTrue((case_dir / "inputs").is_dir())
            self.assertTrue((case_dir / "expected").is_dir())


if __name__ == "__main__":
    unittest.main()
