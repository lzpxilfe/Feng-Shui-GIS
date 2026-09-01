# -*- coding: utf-8 -*-
"""Hyeol candidate spacing and grid helpers for terrain analysis."""

from __future__ import annotations

import math

from qgis.core import QgsPointXY


def combine_hydro_scores(distance_score, dem_score):
    if distance_score is not None and dem_score is not None:
        return (0.7 * distance_score) + (0.3 * dem_score)
    if distance_score is not None:
        return distance_score
    return dem_score


_MAX_SPACING_PASSES = 8


def adaptive_spacing_diagnostics(
    dem_step,
    width,
    height,
    base_step_factor,
    min_span_divisor,
    fallback_spacing,
    max_points,
):
    min_span = min(width, height)
    spacing = max(dem_step * base_step_factor, min_span / min_span_divisor)
    if spacing <= 0:
        spacing = max(dem_step * base_step_factor, fallback_spacing)

    cols = max(1, int(width / spacing) + 1)
    rows = max(1, int(height / spacing) + 1)
    total = cols * rows
    # One sqrt pass solves (w/s)(h/s) == max_points, but each axis carries a
    # trailing +1 node, so the rescaled grid still overshoots the cap.  Repeat
    # until the cap actually holds; spacing grows every pass, so this settles.
    for _ in range(_MAX_SPACING_PASSES):
        if total <= max_points:
            break
        spacing *= math.sqrt(total / max_points)
        cols = max(1, int(width / spacing) + 1)
        rows = max(1, int(height / spacing) + 1)
        total = cols * rows

    return {
        "dem_step": dem_step,
        "width": width,
        "height": height,
        "spacing": spacing,
        "approx_nodes": total,
        "max_points": max_points,
    }


def recommended_hyeol_count(width, height, spacing, thresholds, default_count):
    approx_cols = max(1, int(width / max(spacing, 1e-6)))
    approx_rows = max(1, int(height / max(spacing, 1e-6)))
    approx_nodes = approx_cols * approx_rows
    count = _threshold_value(
        thresholds,
        approx_nodes,
        "count",
        default_count,
    )
    try:
        return max(1, int(count))
    except (TypeError, ValueError):
        return default_count


def grid_points(extent, spacing):
    step = max(float(spacing), 1e-6)
    x_start = extent.xMinimum() + (step * 0.5)
    y_start = extent.yMinimum() + (step * 0.5)
    x = x_start
    while x < extent.xMaximum():
        y = y_start
        while y < extent.yMaximum():
            yield QgsPointXY(x, y)
            y += step
        x += step


def evaluate_hyeol_candidate(
    *,
    point,
    center,
    metrics,
    water_distance,
    slope_value,
    aspect_value,
    hemisphere,
    context,
    profile,
    tpi_min,
    tpi_max,
    score_profile_slope,
    score_aspect,
    score_profile_tpi,
    score_water_distance,
    profile_weighted_score,
):
    tpi_norm = metrics["tpi_norm"]
    if tpi_norm is not None and (tpi_norm < tpi_min or tpi_norm > tpi_max):
        return None

    water_distance_score = score_water_distance(
        water_distance,
        context=context,
    )
    water_score = combine_hydro_scores(
        distance_score=water_distance_score,
        dem_score=metrics["dem_water_score"],
    )

    hyeol_indicators = {
        "slope": score_profile_slope(slope_value, profile),
        "aspect": score_aspect(aspect_value, hemisphere, context=context),
        "form": metrics["form_score"],
        "long": metrics["long_score"],
        "water": water_score,
        "conv": metrics["convergence"],
        "tpi": score_profile_tpi(tpi_norm, profile),
        "sashinsa": metrics.get("sashinsa_score"),
        "enclosure": metrics.get("enclosure_index"),
    }
    hyeol_score = profile_weighted_score(hyeol_indicators, profile)
    if hyeol_score is None or hyeol_score < context["hyeol_threshold"]:
        return None

    return {
        "point": point,
        "score": hyeol_score,
        "elev": center,
        "metrics": metrics,
        "water_distance": water_distance,
        "hydro_score": water_score,
    }


def _threshold_value(rules_list, probe_value, value_key, default_value):
    if not isinstance(rules_list, list):
        return default_value

    candidates = []
    for item in rules_list:
        if not isinstance(item, dict):
            continue
        try:
            min_nodes = int(
                item.get(
                    "min_nodes",
                    item.get("min_candidates", item.get("min_count", 0)),
                )
            )
            value = item.get(value_key, default_value)
        except (TypeError, ValueError):
            continue
        candidates.append((min_nodes, value))

    candidates.sort(key=lambda pair: pair[0], reverse=True)
    for min_nodes, value in candidates:
        if probe_value >= min_nodes:
            return value
    return default_value
