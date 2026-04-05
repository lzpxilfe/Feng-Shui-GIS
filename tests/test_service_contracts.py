import unittest
from dataclasses import FrozenInstanceError, asdict, is_dataclass
from unittest.mock import patch
from hashlib import sha1

from feng_shui_gis.service_contracts import (
    AnalysisOutput,
    AnalysisRequest,
    CalibrationOutput,
    CalibrationRequest,
    CompareRequest,
    ComparisonOutput,
    RunManifest,
    TermExtractionRequest,
    TermExtractionOutput,
)


class ServiceContractTests(unittest.TestCase):
    def test_run_manifest_for_service_has_contract_keys(self):
        with patch("feng_shui_gis.service_contracts.time", return_value=1000.0):
            config_payload = {"a": 1}
            expected_sha = sha1(str(config_payload).encode("utf-8")).hexdigest()
            expected_run_id = sha1(
                f"run_analysis_service|{expected_sha}|42|1000.0".encode("utf-8")
            ).hexdigest()[:12]
            manifest = RunManifest.for_service(
                "run_analysis_service",
                config_payload=config_payload,
                seed=42,
                qgis_version="3.44.8",
                source_layers={"site": {"name": "sites"}},
            )
            payload = manifest.as_dict()

            self.assertEqual(payload["service_name"], "run_analysis_service")
            self.assertEqual(payload["manifest_version"], "1.0.0")
            self.assertEqual(payload["seed"], 42)
            self.assertEqual(payload["qgis_version"], "3.44.8")
            self.assertEqual(payload["source_layers"], {"site": {"name": "sites"}})
            self.assertEqual(payload["config_sha"], expected_sha)
            self.assertEqual(payload["run_id"], expected_run_id)
            self.assertIsInstance(payload["started_at_unix"], float)

    def test_requests_are_dataclass_and_frozen(self):
        self.assertTrue(is_dataclass(AnalysisRequest))
        self.assertTrue(is_dataclass(CompareRequest))
        self.assertTrue(is_dataclass(CalibrationRequest))
        self.assertTrue(is_dataclass(TermExtractionRequest))

        request = AnalysisRequest(
            site_layer="sites",
            dem_layer="dem",
            water_layer=None,
            hemisphere="north",
            profile_key="general",
            culture_key="korea",
            period_key="early_modern",
        )
        with self.assertRaises(FrozenInstanceError):
            request.site_layer = "changed"

    def test_output_contracts_keep_required_payload_keys(self):
        manifest = RunManifest.for_service(
            "run_analysis_service",
            {"ok": True},
            1,
            "3.44",
            {"site_layer": {"name": "sites"}},
        )
        analysis_output = AnalysisOutput(
            manifest=manifest,
            site_layer_name="sites",
            profile_key="general",
            context={"culture": "korea"},
            base_layer_name="base",
            report={"analysis": {}},
            score_stats={},
            warnings=[],
            payloads={},
        )
        comparison_output = ComparisonOutput(
            manifest=manifest,
            site_layer_name="sites",
            base_profile_key="general",
            compare_profile_key="region",
            context={"culture": "korea"},
            base_layer_name="base",
            compare_layer_name="compare",
            top_changes=[],
            selected_change_uids=[],
            score_stats={},
            reports={},
        )
        calibration_output = CalibrationOutput(
            manifest=manifest,
            site_layer_name="sites",
            profile_key="general",
            context={"culture": "korea"},
            calibrated_layer_name="calibrated",
            calibration_fit={"scope": "threshold_only"},
            calibration_report={},
            calibration_applied=False,
            evaluation_enabled=False,
            evaluation_base_metrics={},
            fit_metrics={},
            evaluation_metrics={},
        )
        term_output = TermExtractionOutput(
            manifest=manifest,
            context={"culture": "korea"},
            term_layer_names=["t1"],
            link_layer_names=["l1"],
            metrics={},
            report={},
        )

        self.assertIn("manifest", asdict(analysis_output))
        self.assertIn("top_changes", asdict(comparison_output))
        self.assertIn("calibration_applied", asdict(calibration_output))
        self.assertIn("term_layer_names", asdict(term_output))


if __name__ == "__main__":
    unittest.main()
