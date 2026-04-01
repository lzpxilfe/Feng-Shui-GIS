import configparser
import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class StoreReadinessDocsTests(unittest.TestCase):
    def test_metadata_carries_store_facing_limitations(self):
        parser = configparser.ConfigParser()
        parser.read(ROOT / "feng_shui_gis" / "metadata.txt", encoding="utf-8")
        general = parser["general"]
        text = f"{general.get('description', '')} {general.get('about', '')}".lower()
        self.assertIn("heuristic", text)
        self.assertIn("predictive truth model", text)
        self.assertIn("standalone validation", text)
        self.assertIn("projected crs", text)

    def test_readme_exposes_limitations_and_start_here_links(self):
        text = (ROOT / "README.md").read_text(encoding="utf-8").lower()
        self.assertIn("sample project", text)
        self.assertIn("first run guide", text)
        self.assertIn("tested versions", text)
        self.assertIn("known limitations", text)
        self.assertIn("what this tool is not", text)

    def test_first_run_guide_uses_five_step_path_and_representative_use_cases(self):
        text = (ROOT / "docs" / "first_run_guide.md").read_text(encoding="utf-8").lower()
        self.assertIn("five-step first run", text)
        self.assertIn("1. load the dem.", text)
        self.assertIn("2. select a water layer, or use auto-hydro", text)
        self.assertIn("3. select the candidate point layer.", text)
        self.assertIn("4. run terrain extraction and then site analysis.", text)
        self.assertIn("5. check the result layers and the generated report artifacts.", text)
        self.assertIn("quick terrain reading", text)
        self.assertIn("research compare / calibration", text)
        self.assertIn("support bundle repro sharing", text)

    def test_tested_versions_doc_contains_baseline_and_limitations(self):
        text = (ROOT / "docs" / "tested_versions.md").read_text(encoding="utf-8").lower()
        self.assertIn("ubuntu-latest", text)
        self.assertIn("qgis", text)
        self.assertIn("known limitations", text)
        self.assertIn("projected crs", text)
        self.assertIn("not a predictive truth model", text)

    def test_sample_project_readme_lists_expected_outputs(self):
        text = (
            ROOT / "examples" / "sample_project" / "README.md"
        ).read_text(encoding="utf-8").lower()
        self.assertIn("expected layers", text)
        self.assertIn("fengshui_ridges", text)
        self.assertIn("fengshui_hydro", text)
        self.assertIn("expected report examples", text)


if __name__ == "__main__":
    unittest.main()
