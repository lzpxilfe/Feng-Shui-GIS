"""Contract tests for background comparison of site scores.

A suitability score has no denominator until it is set against what the same
landscape offers at large. These tests pin the statistics that supply it, and
the guards that stop the result being read as more than it is.
"""

import random
import unittest

from feng_shui_gis.null_model import (
    background_comparison,
    background_policy,
    candidate_accepted,
    describe_policy,
    max_attempts,
    cliffs_delta,
    comparison_summary,
    effect_magnitude,
    mean_percentile,
    permutation_test,
)

POLICY = "random land positions, slope < 25 deg, water excluded"


def _sample(mean, sigma, count, seed):
    rng = random.Random(seed)
    return [rng.gauss(mean, sigma) for _ in range(count)]


class CliffsDeltaTests(unittest.TestCase):
    def test_complete_separation_reaches_the_bounds(self):
        self.assertEqual(cliffs_delta([5.0, 6.0, 7.0], [1.0, 2.0, 3.0]), 1.0)
        self.assertEqual(cliffs_delta([1.0, 2.0, 3.0], [5.0, 6.0, 7.0]), -1.0)

    def test_identical_distributions_give_zero(self):
        values = [1.0, 2.0, 3.0, 4.0]
        self.assertEqual(cliffs_delta(values, values), 0.0)

    def test_all_ties_count_as_no_dominance(self):
        self.assertEqual(cliffs_delta([2.0, 2.0], [2.0, 2.0, 2.0]), 0.0)

    def test_delta_matches_the_naive_pairwise_definition(self):
        observed = _sample(0.6, 0.15, 40, seed=11)
        background = _sample(0.45, 0.2, 60, seed=12)
        pairs = [(a, b) for a in observed for b in background]
        naive = (
            sum(1 for a, b in pairs if a > b) - sum(1 for a, b in pairs if a < b)
        ) / len(pairs)
        self.assertAlmostEqual(cliffs_delta(observed, background), naive, places=12)

    def test_empty_input_yields_none(self):
        self.assertIsNone(cliffs_delta([], [1.0]))
        self.assertIsNone(cliffs_delta([1.0], []))

    def test_non_numeric_values_are_dropped(self):
        self.assertEqual(cliffs_delta([5.0, None, "x"], [1.0, 2.0]), 1.0)


class EffectMagnitudeTests(unittest.TestCase):
    def test_bands_follow_the_conventional_thresholds(self):
        self.assertEqual(effect_magnitude(0.9), "large")
        self.assertEqual(effect_magnitude(0.40), "medium")
        self.assertEqual(effect_magnitude(0.20), "small")
        self.assertEqual(effect_magnitude(0.05), "negligible")

    def test_direction_does_not_change_the_band(self):
        self.assertEqual(effect_magnitude(-0.9), "large")

    def test_none_passes_through(self):
        self.assertIsNone(effect_magnitude(None))


class MeanPercentileTests(unittest.TestCase):
    def test_scores_above_everything_sit_at_the_top(self):
        self.assertEqual(mean_percentile([10.0], [1.0, 2.0, 3.0, 4.0]), 1.0)

    def test_scores_below_everything_sit_at_the_bottom(self):
        self.assertEqual(mean_percentile([0.0], [1.0, 2.0, 3.0, 4.0]), 0.0)

    def test_median_score_sits_near_the_middle(self):
        background = [float(value) for value in range(100)]
        self.assertAlmostEqual(mean_percentile([49.5], background), 0.5, delta=0.02)

    def test_ties_are_split_rather_than_favoured(self):
        # A score equal to every background value should land at the midpoint,
        # not at 0.0 or 1.0.
        self.assertEqual(mean_percentile([2.0], [2.0, 2.0, 2.0, 2.0]), 0.5)


class PermutationTestTests(unittest.TestCase):
    def test_separated_groups_produce_a_small_p_value(self):
        result = permutation_test(
            _sample(0.75, 0.08, 30, seed=1),
            _sample(0.45, 0.12, 300, seed=2),
            iterations=2000,
        )
        self.assertLess(result["p_value"], 0.01)

    def test_indistinguishable_groups_produce_a_large_p_value(self):
        result = permutation_test(
            _sample(0.50, 0.12, 30, seed=3),
            _sample(0.50, 0.12, 300, seed=4),
            iterations=2000,
        )
        self.assertGreater(result["p_value"], 0.05)

    def test_p_value_is_never_reported_as_zero(self):
        # A finite number of shuffles cannot demonstrate p = 0, and printing it
        # would overstate the evidence.
        result = permutation_test([100.0] * 20, [0.0] * 200, iterations=200)
        self.assertGreater(result["p_value"], 0.0)
        self.assertAlmostEqual(result["p_value"], 1.0 / 201.0, places=6)

    def test_same_seed_reproduces_the_same_p_value(self):
        args = (_sample(0.6, 0.1, 25, seed=5), _sample(0.5, 0.1, 200, seed=6))
        first = permutation_test(*args, iterations=500, seed=7)
        second = permutation_test(*args, iterations=500, seed=7)
        self.assertEqual(first["p_value"], second["p_value"])

    def test_alternative_direction_is_honoured(self):
        observed = _sample(0.30, 0.08, 30, seed=8)
        background = _sample(0.60, 0.10, 300, seed=9)
        greater = permutation_test(
            observed, background, iterations=1000, alternative="greater"
        )
        less = permutation_test(
            observed, background, iterations=1000, alternative="less"
        )
        self.assertGreater(greater["p_value"], 0.9)
        self.assertLess(less["p_value"], 0.01)

    def test_unknown_alternative_is_rejected(self):
        with self.assertRaises(ValueError):
            permutation_test([1.0, 2.0], [3.0, 4.0], alternative="sideways")

    def test_empty_input_yields_none(self):
        self.assertIsNone(permutation_test([], [1.0, 2.0]))


class BackgroundComparisonTests(unittest.TestCase):
    def test_background_policy_is_mandatory(self):
        # The same delta supports very different claims depending on where the
        # background came from, so the policy cannot be optional.
        with self.assertRaises(ValueError):
            background_comparison([1.0, 2.0], [3.0, 4.0], background_policy="")
        with self.assertRaises(ValueError):
            background_comparison([1.0, 2.0], [3.0, 4.0], background_policy="   ")

    def test_result_carries_the_policy_and_the_claim_limits(self):
        result = background_comparison(
            _sample(0.7, 0.1, 30, seed=21),
            _sample(0.45, 0.12, 400, seed=22),
            background_policy=POLICY,
            iterations=500,
        )
        self.assertTrue(result["usable"])
        self.assertEqual(result["background_policy"], POLICY)
        self.assertIn("does_not_establish", result)
        self.assertIn("feng shui", result["does_not_establish"])

    def test_strong_and_weak_patterns_are_distinguished(self):
        background = _sample(0.45, 0.12, 500, seed=31)
        strong = background_comparison(
            _sample(0.72, 0.10, 30, seed=32),
            background,
            background_policy=POLICY,
            iterations=1000,
        )
        weak = background_comparison(
            _sample(0.47, 0.12, 30, seed=33),
            background,
            background_policy=POLICY,
            iterations=1000,
        )
        self.assertEqual(strong["effect_magnitude"], "large")
        self.assertLess(strong["permutation"]["p_value"], 0.01)
        self.assertIn(weak["effect_magnitude"], ("negligible", "small"))
        self.assertGreater(weak["permutation"]["p_value"], 0.01)

    def test_too_few_samples_reports_unusable_rather_than_a_number(self):
        result = background_comparison(
            [0.7], [0.4, 0.5], background_policy=POLICY
        )
        self.assertFalse(result["usable"])
        self.assertEqual(result["reason"], "insufficient_samples")
        self.assertNotIn("cliffs_delta", result)


class ComparisonSummaryTests(unittest.TestCase):
    def test_summary_states_the_policy_alongside_the_numbers(self):
        result = background_comparison(
            _sample(0.7, 0.1, 30, seed=41),
            _sample(0.45, 0.12, 300, seed=42),
            background_policy=POLICY,
            iterations=500,
        )
        for language in ("ko", "en"):
            summary = comparison_summary(result, language)
            self.assertIn(POLICY, summary)
            self.assertIn("delta", summary.lower())

    def test_unusable_result_says_so_instead_of_reporting_statistics(self):
        result = background_comparison([0.7], [0.4, 0.5], background_policy=POLICY)
        self.assertIn("부족", comparison_summary(result, "ko"))
        self.assertIn("Not enough", comparison_summary(result, "en"))

    def test_non_dict_input_yields_empty_text(self):
        self.assertEqual(comparison_summary(None), "")


if __name__ == "__main__":
    unittest.main()

class BackgroundPolicyTests(unittest.TestCase):
    def test_default_policy_excludes_steep_ground(self):
        # Comparing sites against cliffs makes any pattern look significant.
        policy = background_policy()
        self.assertEqual(policy["max_slope_deg"], 25.0)
        self.assertIn("slope <= 25 deg", policy["description"])

    def test_description_records_every_active_constraint(self):
        policy = background_policy(
            count=500,
            max_slope_deg=20.0,
            exclude_within_m=300.0,
            min_separation_m=100.0,
            seed=7,
        )
        description = policy["description"]
        for fragment in (
            "n=500",
            "slope <= 20 deg",
            "300 m from observed sites",
            "100 m apart",
            "seed=7",
        ):
            self.assertIn(fragment, description)

    def test_inactive_constraints_are_not_claimed(self):
        policy = background_policy(max_slope_deg=None, exclude_within_m=None)
        self.assertNotIn("slope", policy["description"])
        self.assertNotIn("observed sites", policy["description"])

    def test_count_cannot_drop_below_a_comparable_sample(self):
        self.assertEqual(background_policy(count=0)["count"], 2)

    def test_description_of_a_non_policy_is_empty(self):
        self.assertEqual(describe_policy(None), "")


class CandidateAcceptanceTests(unittest.TestCase):
    POLICY = background_policy(
        count=10, max_slope_deg=25.0, exclude_within_m=300.0, min_separation_m=100.0
    )

    def test_unmeasurable_slope_is_rejected(self):
        # Without slope the position cannot be scored the way sites are.
        self.assertFalse(candidate_accepted(self.POLICY, slope_deg=None))

    def test_steep_ground_is_rejected(self):
        self.assertFalse(candidate_accepted(self.POLICY, slope_deg=40.0))

    def test_ground_too_near_an_observed_site_is_rejected(self):
        self.assertFalse(
            candidate_accepted(
                self.POLICY, slope_deg=10.0, distance_to_observed_m=250.0
            )
        )

    def test_ground_too_near_another_draw_is_rejected(self):
        self.assertFalse(
            candidate_accepted(
                self.POLICY, slope_deg=10.0, distance_to_accepted_m=50.0
            )
        )

    def test_a_position_meeting_every_constraint_is_accepted(self):
        self.assertTrue(
            candidate_accepted(
                self.POLICY,
                slope_deg=10.0,
                distance_to_observed_m=900.0,
                distance_to_accepted_m=250.0,
            )
        )

    def test_absent_distances_do_not_reject(self):
        # The first draw has nothing to measure against.
        self.assertTrue(candidate_accepted(self.POLICY, slope_deg=10.0))

    def test_a_non_policy_accepts_nothing(self):
        self.assertFalse(candidate_accepted(None, slope_deg=5.0))


class AttemptCapTests(unittest.TestCase):
    def test_cap_scales_with_the_requested_count(self):
        self.assertGreater(max_attempts(background_policy(count=100)), 100)

    def test_cap_exists_so_an_unsatisfiable_policy_terminates(self):
        # A policy no position can satisfy must stop, not spin.
        self.assertGreater(max_attempts(background_policy(count=1)), 0)
        self.assertEqual(max_attempts(None), 0)

