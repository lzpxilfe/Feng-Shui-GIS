# -*- coding: utf-8 -*-
"""Pure geometry helpers for hyeol-field polygon visualization."""

from __future__ import annotations

import math


def _point_xy(point):
    if point is None:
        return None
    if hasattr(point, "x") and hasattr(point, "y"):
        return (float(point.x()), float(point.y()))
    if isinstance(point, (tuple, list)) and len(point) >= 2:
        return (float(point[0]), float(point[1]))
    return None


def _normalize(dx, dy):
    length = math.hypot(dx, dy)
    if length <= 1e-9:
        return (0.0, 1.0)
    return (dx / length, dy / length)


def _axis_vectors(center_point, front_point=None, azimuth=None):
    center_xy = _point_xy(center_point)
    if center_xy is None:
        return None
    if front_point is not None:
        front_xy = _point_xy(front_point)
        if front_xy is not None:
            dx = front_xy[0] - center_xy[0]
            dy = front_xy[1] - center_xy[1]
            if math.hypot(dx, dy) > 1e-6:
                axis_x, axis_y = _normalize(dx, dy)
                return (center_xy, front_xy, axis_x, axis_y)
    if azimuth is None:
        azimuth = 180.0
    rad = math.radians(float(azimuth))
    axis_x = math.sin(rad)
    axis_y = math.cos(rad)
    front_xy = (center_xy[0] + axis_x, center_xy[1] + axis_y)
    return (center_xy, front_xy, axis_x, axis_y)


def hyeol_field_shape(
    center_point,
    front_point=None,
    *,
    radius_m=None,
    relief_m=None,
    score=None,
    azimuth=None,
):
    """Build an oriented hyeol-field outline around a center point.

    Returns a dict with a closed polygon ring and derived dimensions. The shape
    is intentionally organic: narrower at the back, fuller around the sides, and
    gently opening toward the front.
    """

    axis = _axis_vectors(center_point, front_point=front_point, azimuth=azimuth)
    if axis is None:
        return None
    center_xy, front_xy, axis_x, axis_y = axis
    front_distance = math.hypot(front_xy[0] - center_xy[0], front_xy[1] - center_xy[1])

    relief_value = max(0.0, float(relief_m or 0.0))
    radius_hint = max(front_distance, float(radius_m or 0.0), relief_value * 1.6, 8.0)
    score_value = max(0.0, min(1.0, float(score if score is not None else 0.7)))
    score_scale = 0.92 + (score_value * 0.18)

    front_length = max(radius_hint * 1.12, 8.0) * score_scale
    rear_length = max(radius_hint * 0.62, relief_value * 0.95, 4.0) * score_scale
    field_width = max(radius_hint * 0.78, relief_value * 1.20, 5.0) * score_scale

    half_width = field_width * 0.5
    local_outline = [
        (-rear_length, 0.0),
        (-rear_length * 0.68, half_width * 0.54),
        (-rear_length * 0.24, half_width * 1.02),
        (front_length * 0.18, half_width * 1.30),
        (front_length * 0.72, half_width * 0.94),
        (front_length, 0.0),
        (front_length * 0.72, -half_width * 0.94),
        (front_length * 0.18, -half_width * 1.30),
        (-rear_length * 0.24, -half_width * 1.02),
        (-rear_length * 0.68, -half_width * 0.54),
    ]

    normal_x = -axis_y
    normal_y = axis_x
    ring = []
    for along, across in local_outline:
        ring.append(
            (
                center_xy[0] + (axis_x * along) + (normal_x * across),
                center_xy[1] + (axis_y * along) + (normal_y * across),
            )
        )
    ring.append(ring[0])

    return {
        "ring": ring,
        "front_length": front_length,
        "rear_length": rear_length,
        "field_width": field_width,
        "front_distance": front_distance,
        "azimuth": (math.degrees(math.atan2(axis_x, axis_y)) + 360.0) % 360.0,
    }
