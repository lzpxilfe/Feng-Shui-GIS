import unittest

from feng_shui_gis.analysis_terms import (
    adjusted_term_score,
    term_layer_fields,
    term_runtime_state,
)


class AnalysisTermsContractTests(unittest.TestCase):
    def test_term_layer_fields_expose_expected_schema(self):
        fields = term_layer_fields()
        self.assertGreaterEqual(fields.indexFromName("term_id"), 0)
        self.assertGreaterEqual(fields.indexFromName("reason_ko"), 0)
        self.assertGreaterEqual(fields.indexFromName("radius_m"), 0)

    def test_term_runtime_state_merges_bias_and_builds_radius_map(self):
        state = term_runtime_state(
            context={
                "culture_key": "korea",
                "period_key": "joseon",
                "term_bias": {"ansan": 0.1},
                "term_target_shift": 0.05,
                "hyeol_threshold": 0.6,
                "micro_radius_multiplier": 1.5,
                "macro_radius_multiplier": 2.0,
            },
            profile={"term_bias": {"ansan": 0.05, "jusan": -0.02}},
            dem_step=10.0,
            scales={"inner": 2.0, "outer": 4.0, "far": 6.0},
            min_score_floor=0.42,
            threshold_multiplier=0.72,
        )
        self.assertEqual(state["culture_id"], "korea")
        self.assertEqual(state["period_id"], "joseon")
        self.assertAlmostEqual(state["term_bias"]["ansan"], 0.15)
        self.assertAlmostEqual(state["term_bias"]["jusan"], -0.02)
        self.assertEqual(state["radius_map"]["inner"], 30.0)
        self.assertEqual(state["radius_map"]["outer"], 80.0)

    def test_adjusted_term_score_applies_bias_and_threshold(self):
        self.assertAlmostEqual(
            adjusted_term_score(
                0.5,
                term_id="ansan",
                term_bias={"ansan": 0.1},
                term_min_score=0.55,
            ),
            0.6,
        )
        self.assertIsNone(
            adjusted_term_score(
                0.5,
                term_id="ansan",
                term_bias={},
                term_min_score=0.55,
            )
        )
        self.assertEqual(
            adjusted_term_score(
                0.5,
                term_id="ansan",
                term_bias={},
                term_min_score=0.55,
                mandatory=True,
            ),
            0.5,
        )


if __name__ == "__main__":
    unittest.main()
