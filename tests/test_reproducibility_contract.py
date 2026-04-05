import json
import pathlib
import configparser
import subprocess
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
CONFIG_DIR = ROOT / "feng_shui_gis" / "config"
METADATA_PATH = ROOT / "feng_shui_gis" / "metadata.txt"


def _load_plugin_version():
    parser = configparser.ConfigParser()
    parser.read(METADATA_PATH, encoding="utf-8")
    return parser["general"]["version"]


class ReproducibilityContractTests(unittest.TestCase):
    def test_research_docs_and_templates_exist(self):
        required_paths = [
            ROOT / "docs" / "researcher_quickstart.md",
            ROOT / "docs" / "validation_protocol.md",
            ROOT / "examples" / "README.md",
            ROOT / "examples" / "reproducibility_manifest.template.json",
            ROOT / "tools" / "build_repro_manifest.py",
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
        self.assertIn("run_contract_version", template["run"])
        self.assertIn("random_seed", template["run"])
        self.assertIn("validation_ratio", template["run"])
        self.assertIn("split_seed", template["run"])
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
                "--random-seed",
                "777",
                "--validation-ratio",
                "0.18",
                "--split-seed",
                "2222",
                "--validation-group",
                "cv_holdout",
                "--include-terms",
            ],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        manifest = json.loads(output.stdout)
        self.assertEqual(manifest["dataset"]["id"], "smoke-test")
        self.assertEqual(manifest["plugin"]["version"], _load_plugin_version())
        self.assertEqual(manifest["plugin"]["qgis_version"], "3.40.5")
        self.assertEqual(manifest["run"]["run_contract_version"], "2.0.0")
        self.assertEqual(manifest["run"]["random_seed"], 777)
        self.assertAlmostEqual(manifest["run"]["validation_ratio"], 0.18)
        self.assertEqual(manifest["run"]["split_seed"], 2222)
        self.assertEqual(manifest["run"]["validation_group"], "cv_holdout")
        self.assertEqual(
            {row["path"] for row in manifest["config_snapshot"]},
            {path.relative_to(ROOT).as_posix() for path in sorted(CONFIG_DIR.glob("*.json"))},
        )
        for row in manifest["config_snapshot"]:
            self.assertEqual(len(row["sha256"]), 64)

    def test_manifest_template_contract_fields_are_non_empty_or_expected_defaults(self):
        template = json.loads(
            (ROOT / "examples" / "reproducibility_manifest.template.json").read_text(
                encoding="utf-8"
            )
        )

        dataset = template["dataset"]
        self.assertIn("id", dataset)
        self.assertIn("dem_path", dataset)
        self.assertIn("crs", dataset)

        plugin = template["plugin"]
        self.assertIn("name", plugin)
        self.assertIn("version", plugin)
        self.assertIn("qgis_version", plugin)

        run = template["run"]
        self.assertIn("run_contract_version", run)
        self.assertIsInstance(run["run_contract_version"], str)
        self.assertIsInstance(run["random_seed"], int)
        self.assertIsInstance(run["validation_ratio"], float)
        self.assertIsInstance(run["split_seed"], int)
        self.assertGreater(run["validation_ratio"], 0.0)
        self.assertLess(run["validation_ratio"], 1.0)


if __name__ == "__main__":
    unittest.main()
