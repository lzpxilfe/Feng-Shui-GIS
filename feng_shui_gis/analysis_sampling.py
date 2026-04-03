# -*- coding: utf-8 -*-
"""Pure helpers for calibration point sampling."""

from __future__ import annotations


def negative_sampling_plan(
    *,
    dem_step,
    extent_bounds,
    positive_xy,
    local_padding_factor,
    local_padding_cells,
):
    x_min_extent, x_max_extent, y_min_extent, y_max_extent = extent_bounds
    min_distance = max(
        float(dem_step) * 20.0,
        min(x_max_extent - x_min_extent, y_max_extent - y_min_extent) / 240.0,
    )
    min_distance_sq = min_distance * min_distance
    min_negative_separation_sq = (min_distance * 0.40) ** 2

    x_values = [point[0] for point in positive_xy]
    y_values = [point[1] for point in positive_xy]
    span_x = max(x_values) - min(x_values)
    span_y = max(y_values) - min(y_values)
    local_padding = max(
        min_distance,
        float(dem_step) * float(local_padding_cells),
        max(span_x, span_y) * float(local_padding_factor),
    )
    local_window = (
        max(x_min_extent, min(x_values) - local_padding),
        min(x_max_extent, max(x_values) + local_padding),
        max(y_min_extent, min(y_values) - local_padding),
        min(y_max_extent, max(y_values) + local_padding),
    )
    dem_window = extent_bounds
    search_windows = [local_window]
    if local_window != dem_window:
        search_windows.append(dem_window)
    return {
        "min_distance": min_distance,
        "min_distance_sq": min_distance_sq,
        "min_negative_separation_sq": min_negative_separation_sq,
        "search_windows": search_windows,
    }
