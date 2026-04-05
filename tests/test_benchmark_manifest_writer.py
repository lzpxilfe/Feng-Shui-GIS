import unittest

from feng_shui_gis.reporting.benchmark_manifest_writer import BenchmarkManifestWriter


class BenchmarkManifestWriterTests(unittest.TestCase):
    def test_infers_benchmark_tier_from_run_manifest_feature_counts(self):
        run_manifest = {
            "source_layers": {
                "site": {"feature_count": 1400},
                "dem": {"feature_count": 0},
            },
            "output_layers": {
                "analysis": {"feature_count": 1400},
            },
        }

        tier = BenchmarkManifestWriter.infer_benchmark_tier(
            run_manifest,
            "calibration",
            runtime_seconds=12.0,
        )

        self.assertEqual(tier, "large")

    def test_build_manifest_marks_budget_status(self):
        manifest = BenchmarkManifestWriter.build_manifest(
            dataset_id="smoke-test",
            service_name="analysis",
            qgis_version="3.40.5",
            runtime_seconds=55.0,
            peak_memory_mb=800,
            cancel_latency_ms=1000,
            run_manifest={"run_id": "run-001", "service_name": "analysis"},
            benchmark_tier="small",
            notes="unit-test",
            case_payload={
                "case_id": "gongju_baekje_case",
                "title": "Gongju Baekje study",
                "workflow": ["analysis", "compare", "calibration"],
                "score_drift_tolerance": 0.05,
                "benchmark": {
                    "mode": "descriptive_benchmark",
                    "truth_level": "cluster_level",
                    "water_policy": "auto_hydro_only",
                    "compare_pairs": [
                        {"id": "context_vs_neutral"},
                        {"id": "calibrated_vs_context"},
                    ],
                },
                "expected": {
                    "required_artifacts": {
                        "run_manifest": "reports/run_manifest.json",
                    }
                },
            },
            case_path="/tmp/gongju_baekje_case/case.json",
        )

        self.assertEqual(manifest["dataset"]["benchmark_tier"], "small")
        self.assertEqual(manifest["budget"]["service"], "analysis")
        self.assertEqual(manifest["budget"]["status"], "over_budget")
        self.assertEqual(
            manifest["budget"]["checks"]["runtime_seconds"],
            "over_budget",
        )
        self.assertEqual(manifest["workflow_steps"], ["analysis", "compare", "calibration"])
        self.assertEqual(manifest["score_drift_tolerance"], 0.05)
        self.assertEqual(manifest["case"]["mode"], "descriptive_benchmark")
        self.assertEqual(manifest["case"]["truth_level"], "cluster_level")
        self.assertEqual(manifest["case"]["water_policy"], "auto_hydro_only")
        self.assertEqual(
            manifest["expected_contract"]["required_artifacts"]["run_manifest"],
            "reports/run_manifest.json",
        )


if __name__ == "__main__":
    unittest.main()
