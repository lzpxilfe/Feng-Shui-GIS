import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from feng_shui_gis.study_case_tools import inspect_raster, inspect_vector


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = ROOT / "tests" / "fixtures" / "clear_hydro_case" / "inputs"


class StudyCaseToolsContractTests(unittest.TestCase):
    def test_inspect_vector_reports_polygon_bundle_metadata(self):
        payload = inspect_vector(FIXTURE_DIR / "sample_sites.shp")

        self.assertTrue(payload["exists"])
        self.assertTrue(payload["ready"])
        self.assertEqual(payload["driver"], "ESRI Shapefile")
        self.assertEqual(payload["geometry_type"], "Polygon")
        self.assertGreaterEqual(payload["record_count"], 3)
        self.assertIn("polygon_sites_use_centroid_in_analysis", payload["warnings"])

    def test_inspect_raster_reports_tiff_signature(self):
        payload = inspect_raster(FIXTURE_DIR / "sample_dem.tif")

        self.assertTrue(payload["exists"])
        self.assertTrue(payload["ready"])
        self.assertEqual(payload["driver"], "TIFF")
        self.assertEqual(payload["byte_order"], "little")
        self.assertEqual(payload["tiff_version"], 42)

    def test_setup_study_case_cli_creates_reusable_case_folder(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            case_dir = Path(temp_dir) / "gongju_case"
            result = subprocess.run(
                [
                    "python3",
                    str(ROOT / "tools" / "setup_study_case.py"),
                    str(case_dir),
                    "--dem",
                    str(FIXTURE_DIR / "sample_dem.tif"),
                    "--sites",
                    str(FIXTURE_DIR / "sample_sites.shp"),
                    "--title",
                    "Fixture case",
                    "--profile",
                    "tomb",
                ],
                cwd=ROOT,
                check=True,
                capture_output=True,
                text=True,
            )
            payload = json.loads(result.stdout)

            self.assertTrue(payload["ok"])
            self.assertTrue(payload["analysis_ready"])
            self.assertTrue((case_dir / "case.json").exists())
            self.assertTrue((case_dir / "README.md").exists())
            self.assertTrue((case_dir / "inputs" / "study_sites.shp").exists())
            self.assertTrue((case_dir / "inputs" / "study_sites.dbf").exists())

            case_payload = json.loads((case_dir / "case.json").read_text(encoding="utf-8"))
            self.assertEqual(case_payload["title"], "Fixture case")
            self.assertEqual(case_payload["inputs"]["dem"], "inputs/study_dem.tif")
            self.assertEqual(case_payload["inputs"]["sites"], "inputs/study_sites.shp")
            self.assertTrue(case_payload["run_defaults"]["auto_hydro"])
            self.assertIn("polygon-based", " ".join(payload["warnings"]))


if __name__ == "__main__":
    unittest.main()
