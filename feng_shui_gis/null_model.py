# -*- coding: utf-8 -*-
"""Compare observed site scores against the terrain's own baseline.

A site scoring 0.72 means nothing on its own. If random positions in the same
landscape average 0.68, the pattern is noise dressed as a finding; if they
average 0.41, there is something to explain. Without that reference the score
is a number with no denominator, which is why single-case feng-shui GIS studies
are so hard to compare or reproduce.

This module holds the statistics only — no QGIS, no DEM access — so the
inference can be tested directly. Drawing and scoring the background positions
belongs to the caller, and the policy used to draw them is recorded in the
result because it determines what the comparison can mean.

What a positive result establishes: the observed sites occupy terrain the
model scores differently from the background, under the stated background
policy. What it does not establish: that siting was caused by feng shui, that
the model measures feng shui, or that unsurveyed areas lack sites.
"""

from __future__ import annotations

import bisect
import random
import statistics

ALTERNATIVES = ("greater", "less", "two-sided")

# Conventional reading of |Cliff's delta|. These are descriptive bands from the
# effect-size literature, not significance thresholds.
_EFFECT_BANDS = (
    (0.474, "large"),
    (0.330, "medium"),
    (0.147, "small"),
)


def _clean(values):
    cleaned = []
    for value in values or ():
        try:
            number = float(value)
        except (TypeError, ValueError):
            continue
        if number != number:  # NaN
            continue
        cleaned.append(number)
    return cleaned


def cliffs_delta(observed, background):
    """Probability an observed site outscores a background one, minus reverse.

    Nonparametric, bounded [-1, 1], and meaningful for score distributions that
    are nowhere near normal — which terrain suitability scores generally are.
    """
    a = _clean(observed)
    b = sorted(_clean(background))
    if not a or not b:
        return None
    total = len(a) * len(b)
    dominance = 0
    for value in a:
        lower = bisect.bisect_left(b, value)
        higher = len(b) - bisect.bisect_right(b, value)
        dominance += lower - higher
    return dominance / total


def effect_magnitude(delta):
    """Descriptive band for a Cliff's delta value."""
    if delta is None:
        return None
    magnitude = abs(delta)
    for threshold, label in _EFFECT_BANDS:
        if magnitude >= threshold:
            return label
    return "negligible"


def mean_percentile(observed, background):
    """Average percentile of the observed scores within the background."""
    a = _clean(observed)
    b = sorted(_clean(background))
    if not a or not b:
        return None
    percentiles = []
    for value in a:
        lower = bisect.bisect_left(b, value)
        upper = bisect.bisect_right(b, value)
        # Midpoint of the tied range keeps repeated scores from biasing either way.
        percentiles.append(((lower + upper) / 2.0) / len(b))
    return sum(percentiles) / len(percentiles)


def permutation_test(
    observed, background, *, iterations=10000, seed=42, alternative="greater"
):
    """Monte Carlo permutation test on the difference in means.

    Labels are shuffled across the pooled scores, so this asks whether the
    observed group's mean separates from the background more than an arbitrary
    split of the same values would.
    """
    if alternative not in ALTERNATIVES:
        raise ValueError(f"alternative must be one of {ALTERNATIVES}.")
    a = _clean(observed)
    b = _clean(background)
    if not a or not b:
        return None
    iterations = max(1, int(iterations))

    observed_diff = statistics.fmean(a) - statistics.fmean(b)
    pool = a + b
    n_observed = len(a)
    rng = random.Random(int(seed))

    at_least_as_extreme = 0
    for _ in range(iterations):
        rng.shuffle(pool)
        shuffled_diff = statistics.fmean(pool[:n_observed]) - statistics.fmean(
            pool[n_observed:]
        )
        if alternative == "greater":
            hit = shuffled_diff >= observed_diff
        elif alternative == "less":
            hit = shuffled_diff <= observed_diff
        else:
            hit = abs(shuffled_diff) >= abs(observed_diff)
        if hit:
            at_least_as_extreme += 1

    # Add-one correction: with a finite number of shuffles the true p-value is
    # never exactly zero, and reporting 0.0 overstates the evidence.
    p_value = (at_least_as_extreme + 1) / (iterations + 1)
    return {
        "p_value": p_value,
        "observed_difference": observed_diff,
        "iterations": iterations,
        "seed": int(seed),
        "alternative": alternative,
    }


def background_comparison(
    observed,
    background,
    *,
    background_policy,
    iterations=10000,
    seed=42,
    alternative="greater",
):
    """Full comparison of observed site scores against a background sample.

    ``background_policy`` is required and free-text: it states how the
    background positions were drawn. A comparison against "anywhere in the
    raster" and one against "land under 25 degrees, outside water" support
    completely different claims, and the number alone cannot tell them apart.
    """
    policy = str(background_policy or "").strip()
    if not policy:
        raise ValueError(
            "background_policy is required; the comparison is uninterpretable "
            "without stating how background positions were drawn."
        )

    a = _clean(observed)
    b = _clean(background)
    if len(a) < 2 or len(b) < 2:
        return {
            "usable": False,
            "reason": "insufficient_samples",
            "n_observed": len(a),
            "n_background": len(b),
            "background_policy": policy,
        }

    delta = cliffs_delta(a, b)
    test = permutation_test(
        a, b, iterations=iterations, seed=seed, alternative=alternative
    )
    return {
        "usable": True,
        "n_observed": len(a),
        "n_background": len(b),
        "observed_mean": statistics.fmean(a),
        "background_mean": statistics.fmean(b),
        "observed_median": statistics.median(a),
        "background_median": statistics.median(b),
        "mean_percentile": mean_percentile(a, b),
        "cliffs_delta": delta,
        "effect_magnitude": effect_magnitude(delta),
        "permutation": test,
        "background_policy": policy,
        "establishes": (
            "Observed sites occupy terrain this model scores differently from "
            "background positions drawn under the stated policy."
        ),
        "does_not_establish": (
            "That siting was caused by feng shui, that the model measures feng "
            "shui, that unsurveyed ground lacks sites, or that the result "
            "transfers to another region or period."
        ),
    }


def comparison_summary(result, language="ko"):
    """One-paragraph readout of a background comparison."""
    if not isinstance(result, dict):
        return ""
    if not result.get("usable"):
        if language == "en":
            return (
                "Not enough samples to compare "
                f"(observed {result.get('n_observed', 0)}, "
                f"background {result.get('n_background', 0)})."
            )
        return (
            f"표본이 부족해 비교할 수 없습니다 "
            f"(관측 {result.get('n_observed', 0)}, 배경 {result.get('n_background', 0)})."
        )

    delta = result["cliffs_delta"]
    p_value = result["permutation"]["p_value"]
    if language == "en":
        return (
            f"Observed mean {result['observed_mean']:.3f} vs background "
            f"{result['background_mean']:.3f} "
            f"(n={result['n_observed']} / {result['n_background']}); "
            f"Cliff's delta {delta:+.3f} ({result['effect_magnitude']}), "
            f"permutation p={p_value:.4f}. "
            f"Background policy: {result['background_policy']}."
        )
    return (
        f"관측 평균 {result['observed_mean']:.3f} 대 배경 평균 "
        f"{result['background_mean']:.3f} "
        f"(n={result['n_observed']} / {result['n_background']}), "
        f"Cliff's delta {delta:+.3f}({result['effect_magnitude']}), "
        f"순열검정 p={p_value:.4f}. "
        f"배경 표집 기준: {result['background_policy']}."
    )

DEFAULT_BACKGROUND_COUNT = 800
DEFAULT_MAX_ATTEMPT_FACTOR = 40


def background_policy(
    *,
    count=DEFAULT_BACKGROUND_COUNT,
    max_slope_deg=25.0,
    min_separation_m=None,
    exclude_within_m=None,
    seed=42,
):
    """Rules for drawing background positions, and the text that describes them.

    Defaults exclude ground steeper than 25 degrees, because comparing sites
    against cliffs makes any pattern look significant. Narrowing the policy
    makes the eventual claim stronger and harder to pass, which is the point.

    ``exclude_within_m`` keeps background positions away from the observed
    sites themselves, so the background does not resample the very terrain
    under test.
    """
    policy = {
        "count": max(2, int(count)),
        "max_slope_deg": None if max_slope_deg is None else float(max_slope_deg),
        "min_separation_m": (
            None if min_separation_m is None else float(min_separation_m)
        ),
        "exclude_within_m": (
            None if exclude_within_m is None else float(exclude_within_m)
        ),
        "seed": int(seed),
    }
    policy["description"] = describe_policy(policy)
    return policy


def describe_policy(policy):
    """Human-readable statement of how background positions were drawn."""
    if not isinstance(policy, dict):
        return ""
    parts = [f"random DEM positions n={policy.get('count', 0)}"]
    max_slope = policy.get("max_slope_deg")
    if max_slope is not None:
        parts.append(f"slope <= {max_slope:g} deg")
    exclude_within = policy.get("exclude_within_m")
    if exclude_within:
        parts.append(f"at least {exclude_within:g} m from observed sites")
    min_separation = policy.get("min_separation_m")
    if min_separation:
        parts.append(f"at least {min_separation:g} m apart")
    parts.append("nodata excluded")
    parts.append(f"seed={policy.get('seed')}")
    return ", ".join(parts)


def candidate_accepted(
    policy,
    *,
    slope_deg,
    distance_to_observed_m=None,
    distance_to_accepted_m=None,
):
    """Whether one drawn position satisfies the background policy."""
    if not isinstance(policy, dict):
        return False
    if slope_deg is None:
        # Slope could not be derived, so this position cannot be scored the
        # same way the observed sites are.
        return False
    max_slope = policy.get("max_slope_deg")
    if max_slope is not None and float(slope_deg) > max_slope:
        return False
    exclude_within = policy.get("exclude_within_m")
    if (
        exclude_within
        and distance_to_observed_m is not None
        and float(distance_to_observed_m) < exclude_within
    ):
        return False
    min_separation = policy.get("min_separation_m")
    if (
        min_separation
        and distance_to_accepted_m is not None
        and float(distance_to_accepted_m) < min_separation
    ):
        return False
    return True


def max_attempts(policy, factor=DEFAULT_MAX_ATTEMPT_FACTOR):
    """Attempt cap so an unsatisfiable policy terminates instead of hanging."""
    if not isinstance(policy, dict):
        return 0
    return int(policy.get("count", 0)) * max(1, int(factor))

