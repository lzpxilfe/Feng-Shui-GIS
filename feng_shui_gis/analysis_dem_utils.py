# -*- coding: utf-8 -*-
"""DEM sampling and directional helper utilities for terrain analysis."""

from __future__ import annotations

import math

from qgis.core import QgsPointXY

from .analysis_text import azimuth_label, fmt_num


def sample_dem(provider, point):
    value, ok = provider.sample(point, 1)
    if not ok:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def offset_point(point, distance, azimuth_deg):
    rad = math.radians(azimuth_deg)
    return QgsPointXY(
        point.x() + (distance * math.sin(rad)),
        point.y() + (distance * math.cos(rad)),
    )


def sample_slope_aspect(provider, point, step):
    """Slope in degrees and downhill aspect in compass degrees, from the DEM.

    Horn's 3x3 finite-difference method, the same estimator QGIS and ArcGIS use
    for their slope and aspect rasters.

    Site layers carry pre-computed ``sl_``/``as_`` fields, but background
    positions drawn for a null model have no such fields. Both sides of that
    comparison have to be measured the same way, so this derives them directly.

    Returns ``(slope_deg, aspect_deg)``. Aspect is ``None`` on flat ground,
    where downhill direction is undefined. Both are ``None`` when any cell of
    the window is nodata: substituting the centre value would quietly flatten
    the estimate, and a missing indicator is more honest than a biased one.
    """
    try:
        step = float(step)
    except (TypeError, ValueError):
        return None, None
    if step <= 0.0:
        return None, None

    window = {}
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            sample_point = QgsPointXY(
                point.x() + (dx * step),
                point.y() + (dy * step),
            )
            value = sample_dem(provider, sample_point)
            if value is None:
                return None, None
            window[(dx, dy)] = value

    # x runs east, y runs north.
    west = window[(-1, 1)] + (2.0 * window[(-1, 0)]) + window[(-1, -1)]
    east = window[(1, 1)] + (2.0 * window[(1, 0)]) + window[(1, -1)]
    north = window[(-1, 1)] + (2.0 * window[(0, 1)]) + window[(1, 1)]
    south = window[(-1, -1)] + (2.0 * window[(0, -1)]) + window[(1, -1)]

    dz_dx = (east - west) / (8.0 * step)
    dz_dy = (north - south) / (8.0 * step)

    gradient = math.hypot(dz_dx, dz_dy)
    slope_deg = math.degrees(math.atan(gradient))
    if gradient == 0.0:
        return slope_deg, None

    # The gradient points uphill; aspect is the compass bearing of the
    # downhill direction, measured clockwise from north.
    aspect_deg = math.degrees(math.atan2(-dz_dx, -dz_dy)) % 360.0
    return slope_deg, aspect_deg


def sample_sight_profile(provider, start_point, end_point, step, max_samples=64):
    """Elevation samples along the ray from start to end, endpoints excluded.

    Returns ``(profile, distance)`` where profile is a list of
    ``(distance_m, elevation_m)`` for use with ``analysis_visibility``. Step is
    widened when the span would otherwise need more than ``max_samples``, so a
    distant josan costs the same as a nearby ansan.
    """
    dx = end_point.x() - start_point.x()
    dy = end_point.y() - start_point.y()
    distance = math.hypot(dx, dy)
    if distance <= 0.0:
        return [], 0.0

    try:
        step = float(step)
    except (TypeError, ValueError):
        step = 0.0
    if step <= 0.0:
        step = distance / float(max_samples)
    step = max(step, distance / float(max_samples))

    profile = []
    offset = step
    while offset < distance:
        fraction = offset / distance
        sample_point = QgsPointXY(
            start_point.x() + (dx * fraction),
            start_point.y() + (dy * fraction),
        )
        profile.append((offset, sample_dem(provider, sample_point)))
        offset += step
    return profile, distance


def sample_ring(provider, center_point, radius, azimuths):
    values = []
    for azimuth in azimuths:
        sample_point = offset_point(center_point, radius, azimuth)
        sample_value = sample_dem(provider, sample_point)
        if sample_value is not None:
            values.append(sample_value)
    return values


def mean_scores(*values):
    valid = [v for v in values if v is not None]
    if not valid:
        return None
    return sum(valid) / len(valid)


def stddev(values):
    if not values:
        return None
    if len(values) == 1:
        return 0.0
    mean_value = sum(values) / len(values)
    variance = sum((value - mean_value) ** 2 for value in values) / len(values)
    return math.sqrt(variance)


def direction_mean(provider, center_point, radius, center_azimuth):
    offsets = (-30.0, -15.0, 0.0, 15.0, 30.0)
    values = []
    for offset in offsets:
        azimuth = (center_azimuth + offset) % 360.0
        sample_point = offset_point(center_point, radius, azimuth)
        sample_value = sample_dem(provider, sample_point)
        if sample_value is not None:
            values.append(sample_value)
    if not values:
        return None
    return sum(values) / len(values)
