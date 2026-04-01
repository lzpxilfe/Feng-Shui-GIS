import contextlib
import sys
import types
import unittest


def _install_qgis_stubs():
    if "qgis" in sys.modules:
        return

    qgis_module = types.ModuleType("qgis")
    processing_module = types.ModuleType("qgis.processing")
    processing_module.run = lambda *args, **kwargs: {"OUTPUT": None}

    pyqt_module = types.ModuleType("qgis.PyQt")
    qtcore_module = types.ModuleType("qgis.PyQt.QtCore")
    qtcore_module.QVariant = object

    core_module = types.ModuleType("qgis.core")

    class _Dummy:
        def __init__(self, *args, **kwargs):
            pass

    for name in (
        "QgsCategorizedSymbolRenderer",
        "QgsCoordinateTransform",
        "QgsFeature",
        "QgsField",
        "QgsFields",
        "QgsGeometry",
        "QgsLineSymbol",
        "QgsMarkerSymbol",
        "QgsPointXY",
        "QgsProcessingContext",
        "QgsProcessingFeedback",
        "QgsProcessingUtils",
        "QgsProject",
        "QgsRasterLayer",
        "QgsRendererCategory",
        "QgsSpatialIndex",
        "QgsVectorLayer",
    ):
        setattr(core_module, name, _Dummy)
    core_module.edit = contextlib.nullcontext

    qgis_module.processing = processing_module
    qgis_module.PyQt = pyqt_module
    qgis_module.core = core_module
    pyqt_module.QtCore = qtcore_module

    sys.modules["qgis"] = qgis_module
    sys.modules["qgis.processing"] = processing_module
    sys.modules["qgis.PyQt"] = pyqt_module
    sys.modules["qgis.PyQt.QtCore"] = qtcore_module
    sys.modules["qgis.core"] = core_module


_install_qgis_stubs()

from feng_shui_gis.analysis import FengShuiAnalyzer  # noqa: E402


def _metric_bundle(count, roc_auc, pr_auc):
    return {
        "count": int(count),
        "roc_auc": float(roc_auc),
        "pr_auc": float(pr_auc),
        "best_f1": float(pr_auc),
        "best_f1_threshold": 0.55,
        "best_youden_j": float(roc_auc),
        "best_youden_threshold": 0.65,
    }


class CalibrationContractTests(unittest.TestCase):
    def test_split_rows_is_deterministic_and_non_overlapping(self):
        rows = [
            {"row_id": f"pos-{index}", "label": 1}
            for index in range(10)
        ] + [
            {"row_id": f"neg-{index}", "label": 0}
            for index in range(10)
        ]

        first = FengShuiAnalyzer._split_calibration_rows(
            rows,
            random_seed=42,
            validation_ratio=0.20,
            evaluation_ratio=0.20,
        )
        second = FengShuiAnalyzer._split_calibration_rows(
            rows,
            random_seed=42,
            validation_ratio=0.20,
            evaluation_ratio=0.20,
        )

        first_ids = {
            key: {row["row_id"] for row in value}
            for key, value in first.items()
        }
        second_ids = {
            key: {row["row_id"] for row in value}
            for key, value in second.items()
        }

        self.assertEqual(first_ids, second_ids)
        self.assertTrue(first_ids["train"].isdisjoint(first_ids["validation"]))
        self.assertTrue(first_ids["train"].isdisjoint(first_ids["evaluation"]))
        self.assertTrue(first_ids["validation"].isdisjoint(first_ids["evaluation"]))
        self.assertEqual(
            first_ids["train"] | first_ids["validation"] | first_ids["evaluation"],
            {row["row_id"] for row in rows},
        )

    def test_fit_reports_only_held_out_evaluation_metrics(self):
        split = {
            "train": [
                {"row_id": "train-1", "label": 1},
                {"row_id": "train-2", "label": 0},
            ],
            "validation": [
                {"row_id": "val-1", "label": 1},
                {"row_id": "val-2", "label": 0},
            ],
            "evaluation": [
                {"row_id": "eval-1", "label": 1},
                {"row_id": "eval-2", "label": 0},
            ],
        }
        result = self._run_fit_with_split(split)

        self.assertEqual(result["reported_metric_phase"], "held_out_evaluation")
        self.assertFalse(result["selection_diagnostics"]["reused_for_reporting"])
        self.assertEqual(result["calibration_split"]["train_role"], "fit")
        self.assertEqual(result["calibration_split"]["validation_role"], "selection")
        self.assertEqual(result["calibration_split"]["evaluation_role"], "reported_metrics")
        self.assertTrue(result["calibration_split"]["deterministic_split"])
        self.assertEqual(result["calibration_split"]["selection_count"], 2)
        self.assertEqual(result["calibration_split"]["report_count"], 2)
        self.assertEqual(
            result["selection_diagnostics"]["candidate_metrics"]["roc_auc"],
            0.91,
        )
        self.assertEqual(result["reported_metrics"]["roc_auc"], 0.74)
        self.assertNotEqual(
            result["selection_diagnostics"]["candidate_metrics"]["roc_auc"],
            result["reported_metrics"]["roc_auc"],
        )
        self.assertEqual(
            sorted(result["reported_scores_by_id"].keys()),
            ["eval-1", "eval-2"],
        )

    def test_fit_without_evaluation_rows_exposes_no_reportable_metrics(self):
        split = {
            "train": [
                {"row_id": "train-1", "label": 1},
                {"row_id": "train-2", "label": 0},
            ],
            "validation": [
                {"row_id": "val-1", "label": 1},
                {"row_id": "val-2", "label": 0},
            ],
            "evaluation": [],
        }
        result = self._run_fit_with_split(split)

        self.assertEqual(result["reported_metric_phase"], "no_held_out_evaluation")
        self.assertEqual(result["reported_metrics"]["count"], 0)
        self.assertEqual(result["reported_baseline_metrics"]["count"], 0)
        self.assertEqual(result["calibration_split"]["report_count"], 0)
        self.assertEqual(
            result["selection_diagnostics"]["candidate_metrics"]["roc_auc"],
            0.91,
        )
        self.assertIn("No held-out evaluation rows were available", result["reported_metric_notice"])

    def _run_fit_with_split(self, split):
        all_rows = split["train"] + split["validation"] + split["evaluation"]
        analyzer = FengShuiAnalyzer()

        analyzer._normalized_weight_map = lambda weights: dict(weights)
        analyzer._calibration_rows = lambda layer, profile: list(all_rows)
        analyzer._split_calibration_rows = (
            lambda rows, random_seed, validation_ratio, evaluation_ratio: split
        )
        analyzer._calibration_profile_parameters = lambda profile: {
            "slope_target": float(profile.get("slope_target", 1.0)),
            "slope_sigma": float(profile.get("slope_sigma", 1.0)),
            "tpi_target": float(profile.get("tpi_target", 0.0)),
            "tpi_sigma": float(profile.get("tpi_sigma", 1.0)),
        }
        analyzer._indicator_discrimination = lambda rows, key, profile: {
            "count": len(rows),
            "roc_auc": 0.81,
            "pr_auc": 0.76,
            "quality": 0.62,
        }
        analyzer._parameter_candidate_profiles = lambda model_rows, profile: [
            dict(profile, candidate="candidate")
        ]

        def evaluate(rows, profile):
            ids = tuple(sorted(row["row_id"] for row in rows))
            candidate = profile.get("candidate") == "candidate"
            if not ids:
                return _metric_bundle(0, 0.0, 0.0), {}
            if ids == ("eval-1", "eval-2"):
                metrics = _metric_bundle(2, 0.74 if candidate else 0.59, 0.68 if candidate else 0.51)
            elif ids == ("val-1", "val-2"):
                metrics = _metric_bundle(2, 0.91 if candidate else 0.58, 0.86 if candidate else 0.55)
            elif ids == ("train-1", "train-2"):
                metrics = _metric_bundle(2, 0.88 if candidate else 0.61, 0.81 if candidate else 0.56)
            else:
                metrics = _metric_bundle(len(ids), 0.79 if candidate else 0.60, 0.73 if candidate else 0.55)
            scores = {
                row["row_id"]: (0.85 if candidate else 0.35)
                for row in rows
            }
            return metrics, scores

        def fit_candidate(model_rows, candidate_profile, random_seed=42):
            metrics, scores_by_id = evaluate(model_rows, candidate_profile)
            return {
                "profile": dict(candidate_profile),
                "weights": dict(candidate_profile.get("weights", {})),
                "weight_deltas": {"ridge": 0.15},
                "weight_summary": "ridge:+0.150",
                "indicator_discrimination": {"ridge": {"quality": 0.62}},
                "metrics": metrics,
                "scores_by_id": scores_by_id,
                "weight_applied": True,
            }

        analyzer._evaluate_calibration_rows = evaluate
        analyzer._fit_profile_weight_candidates = fit_candidate

        profile = {
            "weights": {"ridge": 1.0},
            "slope_target": 12.0,
            "slope_sigma": 4.0,
            "tpi_target": 0.2,
            "tpi_sigma": 0.4,
        }
        return analyzer._fit_local_calibration_weights(object(), profile, random_seed=42)


if __name__ == "__main__":
    unittest.main()
