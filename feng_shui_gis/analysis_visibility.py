# -*- coding: utf-8 -*-
"""Line-of-sight tests between a site and the landforms named around it.

Ansan (案山) and josan (朝山) are, by their own definition, hills that are
*looked at* from the site. Until now this plugin picked them by elevation and
distance alone, so a taller ridge sitting between the site and the candidate
did not disqualify it: the term could be assigned to a hill nobody standing at
the site could actually see.

This module answers only the geometric question — is the target above the
horizon formed by the intervening terrain — from an elevation profile. It has
no QGIS imports so the geometry can be tested directly; sampling the profile
off a DEM lives in ``analysis_dem_utils``.

What this does not model: vegetation, buildings, atmospheric visibility, or
whether a visible hill is culturally the right one. It is terrain occlusion.
"""

from __future__ import annotations

import math

EARTH_RADIUS_M = 6371000.0

# Standard atmospheric refraction coefficient for terrestrial sight lines;
# light bends toward the surface, so the effective curvature drop is reduced.
DEFAULT_REFRACTION_K = 0.13

# Eye height of a standing observer. Ansan and josan are read by a person on
# the ground, not from the bare DEM surface.
DEFAULT_OBSERVER_HEIGHT_M = 1.7


def curvature_drop_m(distance_m, refraction_k=DEFAULT_REFRACTION_K):
    """Apparent drop of a distant point from Earth curvature and refraction.

    Negligible for a nearby ansan, but a josan several kilometres out can sit
    metres lower than a flat-earth profile would suggest.
    """
    distance = float(distance_m)
    if distance <= 0.0:
        return 0.0
    return (distance * distance) * (1.0 - float(refraction_k)) / (2.0 * EARTH_RADIUS_M)


def line_of_sight(
    *,
    observer_elev,
    target_elev,
    target_distance_m,
    profile=(),
    observer_height_m=DEFAULT_OBSERVER_HEIGHT_M,
    target_offset_m=0.0,
    refraction_k=DEFAULT_REFRACTION_K,
):
    """Test whether the target clears the terrain horizon from the observer.

    ``profile`` is an iterable of ``(distance_m, elevation_m)`` samples taken
    along the ray. Samples at or beyond the target, and any with a missing
    elevation, are ignored.

    Returns a dict describing the result rather than a bare bool, because the
    interesting part is usually *by how much* and *what blocks it*.
    """
    distance = float(target_distance_m)
    if distance <= 0.0:
        raise ValueError("target_distance_m must be positive.")
    if observer_elev is None or target_elev is None:
        raise ValueError("observer_elev and target_elev are required.")

    eye_elev = float(observer_elev) + float(observer_height_m)

    horizon_slope = -math.inf
    blocked_at_m = None
    used_samples = 0
    for sample in profile:
        try:
            sample_distance, sample_elev = sample
        except (TypeError, ValueError):
            continue
        try:
            sample_distance = float(sample_distance)
            sample_elev = float(sample_elev)
        except (TypeError, ValueError):
            # A nodata cell or a gap in the profile is skipped, not fatal.
            continue
        if sample_distance <= 0.0 or sample_distance >= distance:
            continue
        used_samples += 1
        apparent = sample_elev - curvature_drop_m(sample_distance, refraction_k)
        slope = (apparent - eye_elev) / sample_distance
        if slope > horizon_slope:
            horizon_slope = slope
            blocked_at_m = sample_distance

    target_apparent = (
        float(target_elev)
        + float(target_offset_m)
        - curvature_drop_m(distance, refraction_k)
    )
    target_slope = (target_apparent - eye_elev) / distance

    if horizon_slope == -math.inf:
        # Nothing in between was sampled, so the sight line is unobstructed by
        # anything this profile can speak for.
        return {
            "visible": True,
            "clearance_m": None,
            "blocked_at_m": None,
            "horizon_angle_deg": None,
            "target_angle_deg": math.degrees(math.atan(target_slope)),
            "required_elev_m": None,
            "profile_samples": 0,
        }

    clearance_m = (target_slope - horizon_slope) * distance
    visible = clearance_m > 0.0
    return {
        "visible": visible,
        "clearance_m": clearance_m,
        "blocked_at_m": None if visible else blocked_at_m,
        "horizon_angle_deg": math.degrees(math.atan(horizon_slope)),
        "target_angle_deg": math.degrees(math.atan(target_slope)),
        # Elevation the target would need in order to just clear the horizon.
        "required_elev_m": float(target_elev) - clearance_m,
        "profile_samples": used_samples,
    }


def visibility_summary(result, language="ko"):
    """One-line description of a line-of-sight result for reason text."""
    if not isinstance(result, dict):
        return ""
    if result.get("visible"):
        clearance = result.get("clearance_m")
        if clearance is None:
            if language == "en":
                return "visible (no intervening terrain sampled)"
            return "조망 가능(중간 지형 미표집)"
        if language == "en":
            return f"visible, {clearance:.1f} m above the terrain horizon"
        return f"조망 가능, 지형 능선선 위 {clearance:.1f}m"
    clearance = result.get("clearance_m") or 0.0
    blocked_at = result.get("blocked_at_m")
    if language == "en":
        if blocked_at:
            return (
                f"hidden, {abs(clearance):.1f} m below the horizon "
                f"set at {blocked_at:.0f} m"
            )
        return f"hidden, {abs(clearance):.1f} m below the terrain horizon"
    if blocked_at:
        return f"조망 차단, {blocked_at:.0f}m 지점 능선선 아래 {abs(clearance):.1f}m"
    return f"조망 차단, 지형 능선선 아래 {abs(clearance):.1f}m"
