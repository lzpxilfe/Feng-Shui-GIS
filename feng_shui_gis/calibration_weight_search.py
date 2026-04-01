# -*- coding: utf-8 -*-
"""Pure helpers for calibration weight candidate generation."""

import random


def heuristic_weight_map(base_weights, indicator_discrimination):
    heuristic_weights = {}
    for key, base_value in base_weights.items():
        quality = float((indicator_discrimination.get(key) or {}).get("quality", 0.0))
        heuristic_weights[key] = float(base_value) * (0.20 + quality)
    return heuristic_weights


def focused_weight_map(base_weights, indicator_discrimination, focus_key):
    focused = {}
    for key, base_value in base_weights.items():
        focus_scale = 1.8 if key == focus_key else 0.55
        quality = float((indicator_discrimination.get(key) or {}).get("quality", 0.0))
        quality_scale = 0.35 + quality
        focused[key] = float(base_value) * focus_scale * quality_scale
    return focused


def random_trial_weight_map(base_weights, indicator_discrimination, rng):
    trial_weights = {}
    for key, base_value in base_weights.items():
        quality = float((indicator_discrimination.get(key) or {}).get("quality", 0.0))
        jitter = 0.40 + (rng.random() * 1.80)
        trial_weights[key] = float(base_value) * jitter * (0.25 + quality)
    return trial_weights


def candidate_weight_sets(
    base_weights,
    indicator_discrimination,
    *,
    random_seed=42,
    trial_count=None,
    focus_limit=3,
):
    normalized_base = dict(base_weights or {})
    if not normalized_base:
        return []

    candidates = [dict(normalized_base)]
    candidates.append(heuristic_weight_map(normalized_base, indicator_discrimination))

    ranked_keys = sorted(
        normalized_base.keys(),
        key=lambda item: float((indicator_discrimination.get(item) or {}).get("quality", 0.0)),
        reverse=True,
    )
    for focus_key in ranked_keys[: min(max(0, int(focus_limit)), len(ranked_keys))]:
        candidates.append(
            focused_weight_map(normalized_base, indicator_discrimination, focus_key)
        )

    if trial_count is None:
        trial_count = max(48, len(normalized_base) * 20)
    rng = random.Random(int(random_seed))
    for _ in range(max(0, int(trial_count))):
        candidates.append(
            random_trial_weight_map(normalized_base, indicator_discrimination, rng)
        )
    return candidates


def weight_change_summary(base_weights, final_weights, *, threshold=0.01, max_items=3):
    deltas = {
        key: float(final_weights.get(key, 0.0)) - float(base_weights.get(key, 0.0))
        for key in base_weights.keys()
    }
    changed = sorted(
        (
            (abs(delta), key, delta)
            for key, delta in deltas.items()
            if abs(delta) >= float(threshold)
        ),
        reverse=True,
    )
    if not changed:
        return deltas, "no-material-weight-change"
    summary = ", ".join(
        f"{key}:{delta:+.3f}" for _abs_delta, key, delta in changed[: max(1, int(max_items))]
    )
    return deltas, summary
