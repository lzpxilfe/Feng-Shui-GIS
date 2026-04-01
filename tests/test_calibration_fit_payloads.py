import unittest

from feng_shui_gis.calibration_fit_payloads import (
    calibration_scope,
    calibration_split_manifest,
    parameter_change_summary,
)


class CalibrationFitPayloadTests(unittest.TestCase):
    def test_calibration_split_manifest_records_roles_and_counts(self):
        manifest = calibration_split_manifest(
            total_count=20,
            train_count=12,
            validation_count=4,
            evaluation_count=4,
            used_validation=True,
            used_evaluation=True,
            train_role="fit",
            validation_role="selection",
            evaluation_role="reported_metrics",
            selection_phase="validation",
            reported_metric_phase="held_out_evaluation",
        )

        self.assertTrue(manifest["deterministic_split"])
        self.assertEqual(manifest["train_role"], "fit")
        self.assertEqual(manifest["validation_role"], "selection")
        self.assertEqual(manifest["evaluation_role"], "reported_metrics")
        self.assertEqual(manifest["selection_count"], 4)
        self.assertEqual(manifest["report_count"], 4)

    def test_parameter_change_summary_reports_applied_and_summary(self):
        deltas, summary, applied = parameter_change_summary(
            {"slope_target": 12.0, "tpi_target": 0.2},
            {"slope_target": 13.0, "tpi_target": 0.2},
        )

        self.assertTrue(applied)
        self.assertAlmostEqual(deltas["slope_target"], 1.0)
        self.assertIn("slope_target:+1.000", summary)

    def test_calibration_scope_maps_applied_flags(self):
        self.assertEqual(
            calibration_scope(True, True, True),
            "local_profile_tuning+reweighting",
        )
        self.assertEqual(
            calibration_scope(True, True, False),
            "local_profile_tuning",
        )
        self.assertEqual(
            calibration_scope(True, False, True),
            "local_weight_reweighting",
        )
        self.assertEqual(
            calibration_scope(False, False, False),
            "threshold_only",
        )


if __name__ == "__main__":
    unittest.main()
