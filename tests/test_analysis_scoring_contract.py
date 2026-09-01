import unittest

from feng_shui_gis.analysis_scoring import (
    explain_top_factors,
    indicator_contributions,
    paper_evidence_summary,
    missing_indicator_keys,
    profile_indicator_coverage,
    profile_weighted_score,
)


class AnalysisScoringContractTests(unittest.TestCase):
    def test_profile_weighted_score_uses_available_indicators_only(self):
        score = profile_weighted_score(
            {"slope": 0.8, "water": 0.4, "aspect": None},
            {"weights": {"slope": 0.5, "water": 0.5, "aspect": 0.5}},
        )
        self.assertAlmostEqual(score, 0.6)

    def test_indicator_coverage_tracks_available_weight_share(self):
        confidence = profile_indicator_coverage(
            {"slope": 0.8, "water": None, "aspect": 0.9},
            {"weights": {"slope": 0.5, "water": 0.25, "aspect": 0.25}},
        )
        self.assertAlmostEqual(confidence, 0.75)

    def test_indicator_contributions_sorts_by_weighted_contribution(self):
        rows = indicator_contributions(
            {"slope": 0.9, "water": 0.4, "aspect": 0.7},
            {"weights": {"water": 0.2, "aspect": 0.6, "slope": 0.4}},
        )
        self.assertEqual(rows[0]["key"], "aspect")
        self.assertEqual(rows[-1]["key"], "water")

    def test_explain_top_factors_returns_two_strongest_terms(self):
        summary = explain_top_factors(
            {"slope": 0.9, "water": 0.4, "aspect": 0.7},
            {"weights": {"water": 0.2, "aspect": 0.6, "slope": 0.4}},
        )
        self.assertIn("aspect:0.70", summary)
        self.assertIn("slope:0.90", summary)

    def test_paper_evidence_summary_formats_top_keys_and_refs(self):
        summary = paper_evidence_summary(
            {
                "paper_evidence_records": [
                    {
                        "group": "terrain",
                        "name": "slope_target",
                        "value": 18.0,
                        "evidence_level": "A",
                        "source_doi": ["10.1234/example"],
                    }
                ]
            },
            language="en",
        )
        self.assertIn("terrain.slope_target=+18.00(A)", summary)
        self.assertIn("10.1234/example", summary)


if __name__ == "__main__":
    unittest.main()

class IndicatorCoverageContractTests(unittest.TestCase):
    PROFILE = {"weights": {"slope": 0.4, "water": 0.4, "aspect": 0.2}}

    def test_full_coverage_when_every_indicator_produced_a_value(self):
        coverage = profile_indicator_coverage(
            {"slope": 0.5, "water": 0.5, "aspect": 0.5}, self.PROFILE
        )
        self.assertAlmostEqual(coverage, 1.0)
        self.assertEqual(
            missing_indicator_keys({"slope": 0.5, "water": 0.5, "aspect": 0.5}, self.PROFILE),
            [],
        )

    def test_coverage_is_weight_share_not_indicator_count(self):
        # aspect carries 0.2 of 1.0, so losing it costs 20% of coverage even
        # though it is one of three indicators.
        indicators = {"slope": 0.5, "water": 0.5, "aspect": None}
        self.assertAlmostEqual(
            profile_indicator_coverage(indicators, self.PROFILE), 0.8
        )
        self.assertEqual(missing_indicator_keys(indicators, self.PROFILE), ["aspect"])

    def test_missing_keys_are_sorted_for_stable_output(self):
        indicators = {"slope": None, "water": None, "aspect": None}
        self.assertEqual(
            missing_indicator_keys(indicators, self.PROFILE),
            ["aspect", "slope", "water"],
        )

    def test_coverage_is_none_without_usable_weights(self):
        self.assertIsNone(profile_indicator_coverage({"slope": 0.5}, {"weights": {}}))
        self.assertIsNone(profile_indicator_coverage({"slope": 0.5}, {}))
        self.assertEqual(missing_indicator_keys({}, {"weights": {}}), [])

    def test_coverage_says_nothing_about_the_score_itself(self):
        # A weak site with every indicator present has full coverage; a strong
        # site missing one does not. Coverage is completeness, not quality.
        weak_but_complete = profile_indicator_coverage(
            {"slope": 0.01, "water": 0.01, "aspect": 0.01}, self.PROFILE
        )
        strong_but_partial = profile_indicator_coverage(
            {"slope": 0.99, "water": 0.99, "aspect": None}, self.PROFILE
        )
        self.assertGreater(weak_but_complete, strong_but_partial)

    def test_partial_coverage_signals_a_renormalised_score(self):
        # The score renormalises over available weight, so a partial score can
        # match a full one numerically while resting on less of the model.
        partial = {"slope": 0.8, "water": 0.8, "aspect": None}
        full = {"slope": 0.8, "water": 0.8, "aspect": 0.8}
        self.assertAlmostEqual(
            profile_weighted_score(partial, self.PROFILE),
            profile_weighted_score(full, self.PROFILE),
        )
        self.assertLess(
            profile_indicator_coverage(partial, self.PROFILE),
            profile_indicator_coverage(full, self.PROFILE),
        )

