# -*- coding: utf-8 -*-
"""DEM sampling and directional helper utilities for terrain analysis."""

from __future__ import annotations

import math

from qgis.core import QgsPointXY


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


def fmt_num(value, digits=3):
    if value is None:
        return "n/a"
    return f"{float(value):.{digits}f}"


def azimuth_label(azimuth):
    if azimuth is None:
        return "ring"
    directions = [
        "북",
        "북동",
        "동",
        "남동",
        "남",
        "남서",
        "서",
        "북서",
    ]
    idx = int(((azimuth % 360.0) + 22.5) // 45.0) % 8
    return directions[idx]


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
