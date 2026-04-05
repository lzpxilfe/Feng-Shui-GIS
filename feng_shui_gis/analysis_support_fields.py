# -*- coding: utf-8 -*-
"""Pure geometry helpers for sashinsa and jangpung field visualization."""

from __future__ import annotations

import math


_FIELD_REPLACED_LINK_TYPES = ("outer_wrap", "inner_wrap", "core_axis")


def field_replaced_link_types():
    return set(_FIELD_REPLACED_LINK_TYPES)


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


def _axis_frame(center_point, front_point=None, azimuth=None):
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
                return (center_xy, axis_x, axis_y)
    if azimuth is None:
        azimuth = 180.0
    rad = math.radians(float(azimuth))
    return (center_xy, math.sin(rad), math.cos(rad))


def _project(point, center_xy, axis_x, axis_y):
    point_xy = _point_xy(point)
    if point_xy is None:
        return None
    dx = point_xy[0] - center_xy[0]
    dy = point_xy[1] - center_xy[1]
    normal_x = -axis_y
    normal_y = axis_x
    along = (dx * axis_x) + (dy * axis_y)
    across = (dx * normal_x) + (dy * normal_y)
    return (along, across)


def _compose_ring(center_xy, axis_x, axis_y, outline):
    normal_x = -axis_y
    normal_y = axis_x
    ring = []
    for along, across in outline:
        ring.append(
            (
                center_xy[0] + (axis_x * along) + (normal_x * across),
                center_xy[1] + (axis_y * along) + (normal_y * across),
            )
        )
    ring.append(ring[0])
    return ring


def support_field_shapes(
    center_point,
    *,
    front_point=None,
    rear_point=None,
    left_inner_point=None,
    right_inner_point=None,
    left_outer_point=None,
    right_outer_point=None,
    score=None,
    azimuth=None,
):
    """Build paired sashinsa/jangpung field outlines around a hyeol center."""

    frame = _axis_frame(center_point, front_point=front_point, azimuth=azimuth)
    if frame is None:
        return None
    center_xy, axis_x, axis_y = frame

    front_proj = _project(front_point, center_xy, axis_x, axis_y)
    rear_proj = _project(rear_point, center_xy, axis_x, axis_y)
    left_inner_proj = _project(left_inner_point, center_xy, axis_x, axis_y)
    right_inner_proj = _project(right_inner_point, center_xy, axis_x, axis_y)
    left_outer_proj = _project(left_outer_point, center_xy, axis_x, axis_y)
    right_outer_proj = _project(right_outer_point, center_xy, axis_x, axis_y)

    front_reach = max(
        8.0,
        float(front_proj[0]) if front_proj and front_proj[0] > 0.0 else 0.0,
    )
    rear_depth = max(
        7.0,
        abs(float(rear_proj[0])) if rear_proj and rear_proj[0] < 0.0 else front_reach * 0.55,
    )
    left_inner_span = max(
        5.0,
        float(left_inner_proj[1]) if left_inner_proj and left_inner_proj[1] > 0.0 else front_reach * 0.34,
    )
    right_inner_span = max(
        5.0,
        abs(float(right_inner_proj[1])) if right_inner_proj and right_inner_proj[1] < 0.0 else front_reach * 0.34,
    )
    left_outer_span = max(
        left_inner_span * 1.18,
        float(left_outer_proj[1]) if left_outer_proj and left_outer_proj[1] > 0.0 else 0.0,
    )
    right_outer_span = max(
        right_inner_span * 1.18,
        abs(float(right_outer_proj[1])) if right_outer_proj and right_outer_proj[1] < 0.0 else 0.0,
    )

    score_value = max(0.0, min(1.0, float(score if score is not None else 0.7)))
    score_scale = 0.94 + (score_value * 0.14)

    sashinsa_front_gate = max(front_reach * 0.18, min(left_inner_span, right_inner_span) * 0.22, 3.5) * score_scale
    sashinsa_front_shoulder = max(front_reach * 0.42, sashinsa_front_gate * 1.30) * score_scale
    sashinsa_rear = rear_depth * 1.08 * score_scale
    sashinsa_outline = [
        (-sashinsa_rear, 0.0),
        (-rear_depth * 0.86, left_outer_span * 0.58),
        (-rear_depth * 0.34, left_outer_span * 1.04),
        (sashinsa_front_shoulder, left_inner_span * 1.12),
        (sashinsa_front_gate, left_inner_span * 0.42),
        (sashinsa_front_gate * 0.52, 0.0),
        (sashinsa_front_gate, -right_inner_span * 0.42),
        (sashinsa_front_shoulder, -right_inner_span * 1.12),
        (-rear_depth * 0.34, -right_outer_span * 1.04),
        (-rear_depth * 0.86, -right_outer_span * 0.58),
    ]

    jangpung_front = max(front_reach * 0.24, 2.8) * score_scale
    jangpung_rear = max(rear_depth * 0.64, 5.0) * score_scale
    jangpung_left = left_inner_span * 0.88 * score_scale
    jangpung_right = right_inner_span * 0.88 * score_scale
    jangpung_outline = [
        (-jangpung_rear, 0.0),
        (-jangpung_rear * 0.48, jangpung_left * 0.66),
        (-jangpung_rear * 0.08, jangpung_left * 0.96),
        (jangpung_front, jangpung_left * 0.72),
        (jangpung_front * 0.34, 0.0),
        (jangpung_front, -jangpung_right * 0.72),
        (-jangpung_rear * 0.08, -jangpung_right * 0.96),
        (-jangpung_rear * 0.48, -jangpung_right * 0.66),
    ]

    return {
        "sashinsa": {
            "ring": _compose_ring(center_xy, axis_x, axis_y, sashinsa_outline),
            "front_length": sashinsa_front_shoulder,
            "rear_length": sashinsa_rear,
            "field_width": left_outer_span + right_outer_span,
            "azimuth": (math.degrees(math.atan2(axis_x, axis_y)) + 360.0) % 360.0,
        },
        "jangpung": {
            "ring": _compose_ring(center_xy, axis_x, axis_y, jangpung_outline),
            "front_length": jangpung_front,
            "rear_length": jangpung_rear,
            "field_width": jangpung_left + jangpung_right,
            "azimuth": (math.degrees(math.atan2(axis_x, axis_y)) + 360.0) % 360.0,
        },
    }
