import unittest

from feng_shui_gis.calibration_helpers import (
    build_calibration_report_payload,
    calibration_profile_parameters,
    calibration_scope,
    empty_calibration_fit,
    finalize_calibration_fit,
    normalized_weight_map,
    parameter_candidate_profiles,
    parameter_candidates,
    summarize_named_deltas,
    split_calibration_rows,
)


class CalibrationHelpersContractTests(unittest.TestCase):
    def test_normalized_weight_map_filters_invalid_entries_and_normalizes(self):
        weights = {
            "slope": 2,
            "aspect": "3",
            "water": 0,
            "conv": -1,
            "bad": "x",
        }

        normalized = normalized_weight_map(weights)

        self.assertEqual(set(normalized.keys()), {"slope", "aspect"})
        self.assertAlmostEqual(sum(normalized.values()), 1.0)
        self.assertAlmostEqual(normalized["slope"], 0.4)
        self.assertAlmostEqual(normalized["aspect"], 0.6)

    def test_calibration_profile_parameters_extracts_numeric_fields_only(self):
        profile = {
            "slope_target": "12.5",
            "slope_sigma": 4,
            "tpi_target": "bad",
            "tpi_sigma": 0.08,
            "weights": {"slope": 1},
        }

        self.assertEqual(
            calibration_profile_parameters(profile),
            {
                "slope_target": 12.5,
                "slope_sigma": 4.0,
                "tpi_sigma": 0.08,
            },
        )

    def test_parameter_candidates_include_observed_signal_and_sigma_floor(self):
        rows = [
            {"label": 1, "raw": {"slope": 10.0}},
            {"label": 1, "raw": {"slope": 14.0}},
            {"label": 0, "raw": {"slope": 22.0}},
            {"label": 0, "raw": {"slope": 26.0}},
        ]

        result = parameter_candidates(
            rows,
            "slope",
            base_target=18.0,
            base_sigma=4.0,
            sigma_floor=0.5,
        )

        self.assertEqual(result["stats"]["positive_mean"], 12.0)
        self.assertIn(18.0, result["targets"])
        self.assertIn(12.0, result["targets"])
        self.assertTrue(all(value >= 0.5 for value in result["sigmas"]))
        self.assertLessEqual(len(result["targets"]), 4)
        self.assertLessEqual(len(result["sigmas"]), 4)

    def test_parameter_candidate_profiles_normalize_weights_and_limit_cardinality(self):
        rows = [
            {"label": 1, "raw": {"slope": 8.0, "tpi": 0.10}},
            {"label": 1, "raw": {"slope": 12.0, "tpi": 0.16}},
            {"label": 0, "raw": {"slope": 22.0, "tpi": -0.08}},
            {"label": 0, "raw": {"slope": 25.0, "tpi": -0.12}},
        ]
        profile = {
            "weights": {"slope": 2, "tpi": 1},
            "slope_target": 15.0,
            "slope_sigma": 5.0,
            "tpi_target": 0.02,
            "tpi_sigma": 0.07,
        }

        candidates = parameter_candidate_profiles(rows, profile, max_candidates=8)

        self.assertGreaterEqual(len(candidates), 1)
        self.assertLessEqual(len(candidates), 8)
        first = candidates[0]
        self.assertAlmostEqual(sum(first["weights"].values()), 1.0)
        self.assertIn("slope_target", first)
        self.assertIn("tpi_sigma", first)

    def test_summarize_named_deltas_orders_by_magnitude(self):
        deltas = {"slope": 0.02, "tpi": -0.11, "water": 0.005, "aspect": 0.04}

        summary = summarize_named_deltas(
            deltas,
            threshold=0.01,
            limit=2,
            empty_label="none",
        )

        self.assertEqual(summary, "tpi:-0.110, aspect:+0.040")
        self.assertEqual(
            summarize_named_deltas({}, threshold=0.01, limit=2, empty_label="none"),
            "none",
        )

    def test_calibration_scope_distinguishes_threshold_weight_and_parameter_modes(self):
        self.assertEqual(
            calibration_scope(True, {"slope_target": 0.02}, True),
            "local_profile_tuning+reweighting",
        )
        self.assertEqual(
            calibration_scope(True, {"slope_target": 0.02}, False),
            "local_profile_tuning",
        )
        self.assertEqual(
            calibration_scope(True, {"slope_target": 0.0}, True),
            "local_weight_reweighting",
        )
        self.assertEqual(
            calibration_scope(False, {"slope_target": 0.02}, True),
            "threshold_only",
        )

    def test_empty_calibration_fit_preserves_baseline_contract(self):
        result = empty_calibration_fit(
            base_profile={"weights": {"slope": 0.6, "aspect": 0.4}},
            base_profile_parameters={"slope_target": 12.0},
            base_metrics={"count": 7, "roc_auc": 0.61},
            base_scores_by_id={1: 0.7},
        )

        self.assertFalse(result["applied"])
        self.assertEqual(result["scope"], "threshold_only")
        self.assertEqual(result["weights"], {"slope": 0.6, "aspect": 0.4})
        self.assertEqual(result["base_weights"], {"slope": 0.6, "aspect": 0.4})
        self.assertEqual(result["fit_metrics"], {"count": 7, "roc_auc": 0.61})
        self.assertEqual(result["evaluation_metrics"], {"count": 7, "roc_auc": 0.61})
        self.assertEqual(result["fit_scores_by_id"], {1: 0.7})
        self.assertEqual(result["evaluation_scores_by_id"], {1: 0.7})
        self.assertFalse(result["validation_enabled"])
        self.assertEqual(
            result["split_plan"],
            {
                "mode": "in_sample_single_pool",
                "reason": "step1: fit/eval split is a planned follow-up contract",
            },
        )
        self.assertEqual(result["profile_parameters"], {"slope_target": 12.0})
        self.assertEqual(result["scores_by_id"], {1: 0.7})

    def test_finalize_calibration_fit_uses_best_fit_when_applied(self):
        result = finalize_calibration_fit(
            base_profile={"weights": {"slope": 0.7, "aspect": 0.3}},
            base_profile_parameters={
                "slope_target": 15.0,
                "slope_sigma": 4.0,
            },
            base_metrics={"count": 5, "roc_auc": 0.60},
            base_scores_by_id={1: 0.51},
            best_fit={
                "profile": {
                    "weights": {"slope": 0.9, "aspect": 0.1},
                    "slope_target": 12.0,
                    "slope_sigma": 3.5,
                },
                "weights": {"slope": 0.9, "aspect": 0.1},
                "metrics": {"count": 5, "roc_auc": 0.74},
                "scores_by_id": {1: 0.81},
                "weight_deltas": {"slope": 0.2, "aspect": -0.2},
                "weight_summary": "slope:+0.200, aspect:-0.200",
                "indicator_discrimination": {"slope": {"quality": 0.8}},
                "weight_applied": True,
            },
            applied=True,
        )

        self.assertTrue(result["applied"])
        self.assertEqual(result["scope"], "local_profile_tuning+reweighting")
        self.assertEqual(result["weights"], {"slope": 0.9, "aspect": 0.1})
        self.assertEqual(result["metrics"]["roc_auc"], 0.74)
        self.assertEqual(result["scores_by_id"], {1: 0.81})
        self.assertEqual(result["parameter_deltas"]["slope_target"], -3.0)
        self.assertEqual(result["weight_summary"], "slope:+0.200, aspect:-0.200")
        self.assertEqual(
            result["split_plan"]["mode"],
            "in_sample_single_pool",
        )
        self.assertEqual(
            result["fit_metrics"]["roc_auc"],
            0.74,
        )
        self.assertEqual(
            result["evaluation_metrics"]["roc_auc"],
            0.74,
        )
        self.assertEqual(result["fit_scores_by_id"], {1: 0.81})
        self.assertEqual(result["evaluation_scores_by_id"], {1: 0.81})
        self.assertFalse(result["validation_enabled"])

    def test_split_calibration_rows_is_deterministic_when_seed_is_fixed(self):
        rows = [
            {"row_id": index, "label": index % 2}
            for index in range(20)
        ]
        fit_rows_a, evaluation_rows_a, plan_a = split_calibration_rows(
            rows=rows,
            random_seed=21,
            split_ratio=0.75,
            min_fit_count=6,
            min_eval_count=3,
        )
        fit_rows_b, evaluation_rows_b, plan_b = split_calibration_rows(
            rows=rows,
            random_seed=21,
            split_ratio=0.75,
            min_fit_count=6,
            min_eval_count=3,
        )

        self.assertTrue(plan_a["validation_enabled"])
        self.assertTrue(plan_b["validation_enabled"])
        self.assertEqual(plan_a["fit_count"], len(fit_rows_a))
        self.assertEqual(plan_a["evaluation_count"], len(evaluation_rows_a))
        self.assertEqual(
            {row["row_id"] for row in fit_rows_a},
            {row["row_id"] for row in fit_rows_b},
        )
        self.assertEqual(
            {row["row_id"] for row in evaluation_rows_a},
            {row["row_id"] for row in evaluation_rows_b},
        )
        self.assertEqual(
            set(row["row_id"] for row in fit_rows_a).intersection(
                row["row_id"] for row in evaluation_rows_a
            ),
            set(),
        )

    def test_split_calibration_rows_disables_validation_when_rows_are_insufficient(self):
        rows = [
            {"row_id": index, "label": index % 2}
            for index in range(7)
        ]
        fit_rows, evaluation_rows, plan = split_calibration_rows(
            rows=rows,
            random_seed=11,
            split_ratio=0.75,
            min_fit_count=6,
            min_eval_count=3,
        )

        self.assertFalse(plan["validation_enabled"])
        self.assertFalse(fit_rows is None)
        self.assertEqual(len(evaluation_rows), 0)
        self.assertGreater(len(fit_rows), 0)

    def test_build_calibration_report_payload_maps_fit_to_report_schema(self):
        report = build_calibration_report_payload(
            context={
                "culture_key": "korea",
                "period_key": "early_modern",
                "evidence": {"parameters": {"aspect_target": 180.0}},
            },
            profile={"paper_evidence_records": [{"title": "A"}]},
            profile_key="general",
            hemisphere="north",
            site_layer_name="sites",
            site_metadata_summary={"count": 3},
            negative_ratio=3,
            random_seed=42,
            positive_count=10,
            negative_count=30,
            calibration_fit={
                "scope": "local_weight_reweighting",
                "applied": True,
                "weights": {"slope": 0.8},
                "base_weights": {"slope": 1.0},
                "weight_deltas": {"slope": -0.2},
                "weight_summary": "slope:-0.200",
                "profile_parameters": {"slope_target": 11.0},
                "base_profile_parameters": {"slope_target": 13.0},
                "parameter_deltas": {"slope_target": -2.0},
                "parameter_summary": "slope_target:-2.000",
                "indicator_discrimination": {"slope": {"quality": 0.7}},
                "metrics": {
                    "count": 40,
                    "roc_auc": 0.79,
                    "pr_auc": 0.71,
                    "best_f1": 0.66,
                    "best_f1_threshold": 0.63,
                    "best_youden_j": 0.44,
                    "best_youden_threshold": 0.63,
                },
                "base_metrics": {
                    "count": 40,
                    "roc_auc": 0.68,
                    "pr_auc": 0.57,
                    "best_f1": 0.55,
                    "best_f1_threshold": 0.59,
                    "best_youden_j": 0.31,
                    "best_youden_threshold": 0.59,
                },
            },
            paper_evidence_summary="2 papers",
        )

        self.assertEqual(report["culture_key"], "korea")
        self.assertEqual(report["calibration_scope"], "local_weight_reweighting")
        self.assertTrue(report["calibration_applied"])
        self.assertEqual(report["valid_count"], 40)
        self.assertEqual(report["base_valid_count"], 40)
        self.assertEqual(report["tuned_weight_summary"], "slope:-0.200")
        self.assertEqual(report["tuned_parameter_summary"], "slope_target:-2.000")
        self.assertEqual(report["paper_evidence_summary"], "2 papers")
        self.assertEqual(report["paper_evidence_records"], [{"title": "A"}])
        self.assertEqual(report["evidence_parameters"], {"aspect_target": 180.0})
        self.assertEqual(report["calibration_split_mode"], "in_sample_single_pool")
        self.assertFalse(report["calibration_validation_enabled"])
        self.assertEqual(report["fit_count"], 40)
        self.assertEqual(report["evaluation_count"], 40)
        self.assertEqual(report["fit_roc_auc"], 0.79)
        self.assertEqual(report["evaluation_roc_auc"], 0.79)
        self.assertEqual(report["calibration_split_reason"], "")


if __name__ == "__main__":
    unittest.main()
