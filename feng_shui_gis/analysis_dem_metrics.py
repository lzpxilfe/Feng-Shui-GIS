# -*- coding: utf-8 -*-
"""Derived DEM metric helpers for terrain scoring."""

from __future__ import annotations


def null_dem_metrics():
    return {
        "form_score": None,
        "long_score": None,
        "dem_water_score": None,
        "tpi_norm": None,
        "convergence": None,
        "sashinsa_score": None,
        "enclosure_index": None,
        "large_tpi_norm": None,
        "roughness": None,
        "cut_depth": None,
    }


def sampling_setup(*, dem_step, sampling_rules, context):
    micro_mult = 1.0
    macro_mult = 1.0
    if context:
        micro_mult = float(context["micro_radius_multiplier"])
        macro_mult = float(context["macro_radius_multiplier"])
    micro_radius = dem_step * float(sampling_rules["micro_radius_factor"]) * micro_mult
    macro_radius = dem_step * float(sampling_rules["macro_radius_factor"]) * macro_mult

    macro_bearing_step = int(sampling_rules["macro_bearing_step"])
    micro_bearing_step = int(sampling_rules["micro_bearing_step"])
    macro_bearings = list(range(0, 360, max(1, macro_bearing_step)))
    micro_bearings = list(range(0, 360, max(1, micro_bearing_step)))
    return {
        "micro_radius": micro_radius,
        "macro_radius": macro_radius,
        "macro_bearings": macro_bearings,
        "micro_bearings": micro_bearings,
    }


def relief_statistics(*, macro_values, micro_values, stddev_fn):
    relief = None
    mean_macro = None
    std_macro = None
    std_micro = None
    if macro_values:
        relief = max(macro_values) - min(macro_values)
        mean_macro = sum(macro_values) / len(macro_values)
        std_macro = stddev_fn(macro_values)
    if micro_values:
        std_micro = stddev_fn(micro_values)
    return {
        "relief": relief,
        "mean_macro": mean_macro,
        "std_macro": std_macro,
        "std_micro": std_micro,
    }


def compute_form_score(
    *,
    center,
    relief,
    back_mean,
    front_mean,
    left_mean,
    right_mean,
    dem_rules,
    score_gaussian,
    mean_scores,
):
    if (
        relief is None
        or relief <= 0
        or back_mean is None
        or front_mean is None
        or left_mean is None
        or right_mean is None
    ):
        return None

    back_norm = (back_mean - center) / relief
    front_norm = (center - front_mean) / relief
    side_norm = (left_mean - right_mean) / relief

    back_spec = dem_rules["form_back"]
    front_spec = dem_rules["form_front"]
    side_spec = dem_rules["form_side"]
    back_score = score_gaussian(
        back_norm, float(back_spec["target"]), float(back_spec["sigma"])
    )
    front_score = score_gaussian(
        front_norm, float(front_spec["target"]), float(front_spec["sigma"])
    )
    side_score = score_gaussian(
        side_norm, float(side_spec["target"]), float(side_spec["sigma"])
    )
    return mean_scores(back_score, front_score, side_score)


def compute_long_score(
    *,
    center,
    relief,
    mean_macro,
    std_micro,
    std_macro,
    dem_rules,
    score_gaussian,
    mean_scores,
):
    if relief is None or relief <= 0 or mean_macro is None:
        return None, None

    tpi = center - mean_macro
    tpi_norm = tpi / relief
    xue_spec = dem_rules["xue"]
    xue_score = score_gaussian(
        tpi_norm, float(xue_spec["target"]), float(xue_spec["sigma"])
    )
    hierarchy_ratio = None
    if std_micro is not None and std_macro is not None and std_macro > 0:
        hierarchy_ratio = std_micro / std_macro
    hierarchy_spec = dem_rules["hierarchy"]
    hierarchy_score = score_gaussian(
        hierarchy_ratio,
        float(hierarchy_spec["target"]),
        float(hierarchy_spec["sigma"]),
    )
    return mean_scores(xue_score, hierarchy_score), tpi_norm


def compute_dem_water_score(
    *,
    center,
    micro_values,
    slope_deg,
    dem_rules,
    score_gaussian,
):
    if not micro_values:
        return None, None

    higher = sum(max(value - center, 0.0) for value in micro_values)
    lower = sum(max(center - value, 0.0) for value in micro_values)
    convergence = higher / (higher + lower + 1e-6)

    if slope_deg is None:
        slope_factor = 0.75
    else:
        slope_denominator = float(dem_rules["slope_denominator"])
        slope_factor = max(0.25, 1.0 - min(1.0, slope_deg / slope_denominator))

    wetness_spec = dem_rules["wetness"]
    wetness_shape = score_gaussian(
        convergence,
        float(wetness_spec["target"]),
        float(wetness_spec["sigma"]),
    )
    dem_water_score = max(0.0, min(1.0, wetness_shape * (0.6 + 0.4 * slope_factor)))
    return dem_water_score, convergence


def compute_sashinsa_score(
    *,
    center,
    relief,
    back_mean,
    front_mean,
    left_mean,
    right_mean,
    sashinsa_rules,
    score_gaussian,
):
    if (
        back_mean is None
        or front_mean is None
        or left_mean is None
        or right_mean is None
        or relief is None
        or relief <= 0
    ):
        return None

    back_tgt = float(sashinsa_rules.get("back_target_ratio", 0.12))
    back_sig = max(0.01, float(sashinsa_rules.get("back_sigma", 0.18)))
    front_tgt = float(sashinsa_rules.get("front_target_ratio", -0.10))
    front_sig = max(0.01, float(sashinsa_rules.get("front_sigma", 0.18)))
    side_tgt = float(sashinsa_rules.get("side_target_ratio", 0.06))
    side_sig = max(0.01, float(sashinsa_rules.get("side_sigma", 0.15)))
    scores = [
        score_gaussian((back_mean - center) / relief, back_tgt, back_sig),
        score_gaussian((front_mean - center) / relief, front_tgt, front_sig),
        score_gaussian((left_mean - center) / relief, side_tgt, side_sig),
        score_gaussian((right_mean - center) / relief, side_tgt, side_sig),
    ]
    valid = [value for value in scores if value is not None]
    if not valid:
        return None
    product = 1.0
    for value in valid:
        product *= max(1e-9, value)
    return product ** (1.0 / len(valid))


def compute_enclosure_index(
    *,
    center,
    macro_values,
    enclosure_rules,
    score_gaussian,
):
    if not macro_values:
        return None

    enc_tgt = float(enclosure_rules.get("target_ratio", 0.62))
    enc_sig = max(0.01, float(enclosure_rules.get("sigma", 0.22)))
    higher = sum(1 for value in macro_values if value > center)
    enc_ratio = higher / len(macro_values)
    return score_gaussian(enc_ratio, enc_tgt, enc_sig)


def compute_roughness(std_macro, relief):
    if std_macro is None or relief is None or relief <= 0:
        return None
    return min(1.0, std_macro / relief)


def compute_cut_depth(macro_values, center, relief):
    if not macro_values or relief is None or relief <= 0:
        return None
    max_macro_val = max(macro_values)
    return max(0.0, min(2.0, (max_macro_val - center) / relief))
