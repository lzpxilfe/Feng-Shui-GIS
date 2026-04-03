# -*- coding: utf-8 -*-
"""Pure helpers for terrain-network rule calculations."""

from __future__ import annotations

import math


def compute_hydro_spacing(
    *,
    dem_step,
    coarse_spacing,
    width,
    height,
    spacing_step_factor,
    spacing_coarse_factor,
    spacing_fallback,
    max_points,
):
    spacing = max(
        float(dem_step) * float(spacing_step_factor),
        float(coarse_spacing) * float(spacing_coarse_factor),
    )
    if spacing <= 0:
        spacing = max(float(dem_step) * float(spacing_step_factor), float(spacing_fallback))
    cols = max(1, int(float(width) / spacing) + 1)
    rows = max(1, int(float(height) / spacing) + 1)
    total = cols * rows
    if total > int(max_points):
        spacing *= math.sqrt(total / float(max_points))
    return spacing


def clamp_quantile(value, default_quantile=0.86):
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return float(default_quantile)


def clamp_min_order(value, default_order=2):
    try:
        return max(1, int(value))
    except (TypeError, ValueError):
        return int(default_order)


def compute_hydro_min_path_length(
    *,
    width,
    height,
    spacing,
    base_spacing_factor,
    base_diag_ratio,
    node_spacing_factor=None,
):
    diag = math.hypot(float(width), float(height))
    length = max(float(spacing) * float(base_spacing_factor), diag * float(base_diag_ratio))
    if node_spacing_factor is not None:
        try:
            length = max(length, float(spacing) * max(0.1, float(node_spacing_factor)))
        except (TypeError, ValueError):
            pass
    return length
