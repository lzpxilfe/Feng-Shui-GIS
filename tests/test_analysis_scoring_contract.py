import unittest

from feng_shui_gis.analysis_scoring import (
    explain_top_factors,
    indicator_contributions,
    paper_evidence_summary,
    profile_confidence,
    profile_weighted_score,
)


class AnalysisScoringContractTests(unittest.TestCase):
    def test_profile_weighted_score_uses_available_indicators_only(self):
        score = profile_weighted_score(
            {"slope": 0.8, "water": 0.4, "aspect": None},
            {"weights": {"slope": 0.5, "water": 0.5, "aspect": 0.5}},
        )
        self.assertAlmostEqual(score, 0.6)

    def test_profile_confidence_tracks_available_weight_share(self):
        confidence = profile_confidence(
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
