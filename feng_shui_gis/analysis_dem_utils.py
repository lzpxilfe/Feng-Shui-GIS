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
