# -*- coding: utf-8 -*-
"""Chinese datum and projection helpers.

Chinese web map services publish coordinates in one of two obfuscated datums:

* **GCJ-02** (国测局坐标, "Mars coordinates") — used by Amap/Gaode, Tencent, and
  Google's China tiles. Offset from WGS84 by roughly 100-700 m.
* **BD-09** (百度坐标) — Baidu's further offset on top of GCJ-02.

Neither declares itself. A layer digitised from a Chinese basemap reports
EPSG:4326 exactly like a WGS84 layer does, so nothing in the file identifies
the shift. On a 30 m DEM a GCJ-02 mix-up moves a candidate site by ten or more
cells, which silently invalidates every ridge, water, and enclosure reading
taken there.

This module is deliberately free of QGIS imports so the geodesy can be tested
directly. The transforms are the widely published closed-form approximations;
they are accurate to a few metres, which is what the offset detection needs,
and they are *not* a survey-grade datum transformation.
"""

from __future__ import annotations

import math

# Krasovsky 1940 ellipsoid, which the GCJ-02 obfuscation is defined against.
_A = 6378245.0
_EE = 0.00669342162296594323
_X_PI = math.pi * 3000.0 / 180.0

# Bounding box outside which GCJ-02 is defined to equal WGS84. This is the
# conventional box used by the published implementations; it is deliberately
# generous and is not a statement about any territorial boundary.
CHINA_BOUNDS = (73.66, 3.86, 135.05, 53.55)

# Mainland-scale box used to decide whether to raise the datum advisory at all.
_ADVISORY_BOUNDS = (73.0, 3.5, 135.5, 53.6)

# The advisory box unavoidably reaches over neighbouring countries whose data
# never uses GCJ-02. Suppressing those keeps the warning meaningful for this
# plugin's Korea-first user base. These are noise-suppression regions for a UI
# hint, not a statement about any border; they are kept deliberately small so
# that ambiguous areas near a frontier still get the advisory rather than
# silently losing it.
_ADVISORY_EXCLUSIONS = (
    ("korean_peninsula", (125.5, 33.0, 130.0, 41.5)),
    ("japan", (129.0, 30.0, 146.0, 46.0)),
)

CGCS2000_GEOGRAPHIC_EPSG = 4490

# EPSG blocks for CGCS2000 projected systems. China's national standard uses
# 3-degree Gauss-Kruger belts for large-scale work (1:10 000 and finer), which
# is the regime terrain analysis falls into.
_GK3_CM_BASE_EPSG = 4534  # CGCS2000 / 3-degree Gauss-Kruger CM 75E
_GK3_CM_MIN_DEG = 75
_GK3_CM_MAX_DEG = 135
_GK3_CM_STEP_DEG = 3

_GK6_CM_BASE_EPSG = 4502  # CGCS2000 / Gauss-Kruger CM 75E
_GK6_CM_MIN_DEG = 75
_GK6_CM_MAX_DEG = 135
_GK6_CM_STEP_DEG = 6

# Equal-area projection for extents too wide for a single Gauss-Kruger belt.
CHINA_ALBERS_PROJ4 = (
    "+proj=aea +lat_1=25 +lat_2=47 +lat_0=0 +lon_0=105 "
    "+x_0=0 +y_0=0 +ellps=GRS80 +units=m +no_defs"
)


def out_of_china(lon, lat):
    """True when GCJ-02 is defined to coincide with WGS84 at this position."""
    min_lon, min_lat, max_lon, max_lat = CHINA_BOUNDS
    return not (min_lon <= lon <= max_lon and min_lat <= lat <= max_lat)


def _within(lon, lat, box):
    min_lon, min_lat, max_lon, max_lat = box
    return min_lon <= lon <= max_lon and min_lat <= lat <= max_lat


def in_china_advisory_area(lon, lat):
    """True when a Chinese-datum mix-up is plausible at this position."""
    lon = float(lon)
    lat = float(lat)
    if not _within(lon, lat, _ADVISORY_BOUNDS):
        return False
    return not any(
        _within(lon, lat, box) for _name, box in _ADVISORY_EXCLUSIONS
    )


def _transform_lat(x, y):
    ret = (
        -100.0
        + 2.0 * x
        + 3.0 * y
        + 0.2 * y * y
        + 0.1 * x * y
        + 0.2 * math.sqrt(abs(x))
    )
    ret += (
        20.0 * math.sin(6.0 * x * math.pi) + 20.0 * math.sin(2.0 * x * math.pi)
    ) * 2.0 / 3.0
    ret += (
        20.0 * math.sin(y * math.pi) + 40.0 * math.sin(y / 3.0 * math.pi)
    ) * 2.0 / 3.0
    ret += (
        160.0 * math.sin(y / 12.0 * math.pi) + 320.0 * math.sin(y * math.pi / 30.0)
    ) * 2.0 / 3.0
    return ret


def _transform_lon(x, y):
    ret = (
        300.0
        + x
        + 2.0 * y
        + 0.1 * x * x
        + 0.1 * x * y
        + 0.1 * math.sqrt(abs(x))
    )
    ret += (
        20.0 * math.sin(6.0 * x * math.pi) + 20.0 * math.sin(2.0 * x * math.pi)
    ) * 2.0 / 3.0
    ret += (
        20.0 * math.sin(x * math.pi) + 40.0 * math.sin(x / 3.0 * math.pi)
    ) * 2.0 / 3.0
    ret += (
        150.0 * math.sin(x / 12.0 * math.pi) + 300.0 * math.sin(x / 30.0 * math.pi)
    ) * 2.0 / 3.0
    return ret


def wgs84_to_gcj02(lon, lat):
    """WGS84 -> GCJ-02 (Amap / Tencent / Google China)."""
    lon = float(lon)
    lat = float(lat)
    if out_of_china(lon, lat):
        return lon, lat
    d_lat = _transform_lat(lon - 105.0, lat - 35.0)
    d_lon = _transform_lon(lon - 105.0, lat - 35.0)
    rad_lat = lat / 180.0 * math.pi
    magic = math.sin(rad_lat)
    magic = 1.0 - _EE * magic * magic
    sqrt_magic = math.sqrt(magic)
    d_lat = (d_lat * 180.0) / ((_A * (1.0 - _EE)) / (magic * sqrt_magic) * math.pi)
    d_lon = (d_lon * 180.0) / (_A / sqrt_magic * math.cos(rad_lat) * math.pi)
    return lon + d_lon, lat + d_lat


def gcj02_to_wgs84(lon, lat, iterations=4):
    """GCJ-02 -> WGS84 by fixed-point refinement of the forward transform.

    The forward transform has no closed-form inverse. Four iterations bring the
    residual well under a millimetre, far below the accuracy of the published
    approximation itself.
    """
    lon = float(lon)
    lat = float(lat)
    if out_of_china(lon, lat):
        return lon, lat
    guess_lon, guess_lat = lon, lat
    for _ in range(max(1, int(iterations))):
        fwd_lon, fwd_lat = wgs84_to_gcj02(guess_lon, guess_lat)
        guess_lon += lon - fwd_lon
        guess_lat += lat - fwd_lat
    return guess_lon, guess_lat


def gcj02_to_bd09(lon, lat):
    """GCJ-02 -> BD-09 (Baidu)."""
    lon = float(lon)
    lat = float(lat)
    z = math.sqrt(lon * lon + lat * lat) + 0.00002 * math.sin(lat * _X_PI)
    theta = math.atan2(lat, lon) + 0.000003 * math.cos(lon * _X_PI)
    return z * math.cos(theta) + 0.0065, z * math.sin(theta) + 0.006


def bd09_to_gcj02(lon, lat):
    """BD-09 -> GCJ-02."""
    x = float(lon) - 0.0065
    y = float(lat) - 0.006
    z = math.sqrt(x * x + y * y) - 0.00002 * math.sin(y * _X_PI)
    theta = math.atan2(y, x) - 0.000003 * math.cos(x * _X_PI)
    return z * math.cos(theta), z * math.sin(theta)


def wgs84_to_bd09(lon, lat):
    return gcj02_to_bd09(*wgs84_to_gcj02(lon, lat))


def bd09_to_wgs84(lon, lat):
    return gcj02_to_wgs84(*bd09_to_gcj02(lon, lat))


TRANSFORMS = {
    ("wgs84", "gcj02"): wgs84_to_gcj02,
    ("gcj02", "wgs84"): gcj02_to_wgs84,
    ("gcj02", "bd09"): gcj02_to_bd09,
    ("bd09", "gcj02"): bd09_to_gcj02,
    ("wgs84", "bd09"): wgs84_to_bd09,
    ("bd09", "wgs84"): bd09_to_wgs84,
}

SUPPORTED_DATUMS = ("wgs84", "gcj02", "bd09")


def transform(lon, lat, source_datum, target_datum):
    """Convert one position between the supported Chinese datums."""
    source = str(source_datum or "").strip().lower()
    target = str(target_datum or "").strip().lower()
    for name in (source, target):
        if name not in SUPPORTED_DATUMS:
            raise ValueError(
                f"Unsupported datum '{name}'; expected one of {SUPPORTED_DATUMS}."
            )
    if source == target:
        return float(lon), float(lat)
    return TRANSFORMS[(source, target)](lon, lat)


def _meters_per_degree(lat):
    rad_lat = float(lat) / 180.0 * math.pi
    lat_m = 111132.92 - 559.82 * math.cos(2 * rad_lat) + 1.175 * math.cos(4 * rad_lat)
    lon_m = 111412.84 * math.cos(rad_lat) - 93.5 * math.cos(3 * rad_lat)
    return lon_m, lat_m


def gcj02_offset_meters(lon, lat):
    """Ground distance between the same point expressed in WGS84 and GCJ-02."""
    shifted_lon, shifted_lat = wgs84_to_gcj02(lon, lat)
    lon_m, lat_m = _meters_per_degree(lat)
    dx = (shifted_lon - float(lon)) * lon_m
    dy = (shifted_lat - float(lat)) * lat_m
    return math.hypot(dx, dy)


def bd09_offset_meters(lon, lat):
    """Ground distance between the same point expressed in WGS84 and BD-09."""
    shifted_lon, shifted_lat = wgs84_to_bd09(lon, lat)
    lon_m, lat_m = _meters_per_degree(lat)
    dx = (shifted_lon - float(lon)) * lon_m
    dy = (shifted_lat - float(lat)) * lat_m
    return math.hypot(dx, dy)


def _gauss_kruger_cm(lon, step_deg, min_deg, max_deg):
    central = int(round(float(lon) / step_deg) * step_deg)
    return max(min_deg, min(max_deg, central))


def recommended_projected_crs(lon, lat, extent_width_deg=None):
    """Suggest a metre-based CRS for terrain work at this position.

    Returns a dict with ``authid`` (or ``proj4`` for the wide-extent case),
    ``label``, and ``reason``. Nothing here is applied automatically; the
    caller shows it so the user can reproject deliberately.
    """
    if not in_china_advisory_area(float(lon), float(lat)):
        return None

    # A single 3-degree belt stops being appropriate once the extent spans more
    # than about one belt; beyond that an equal-area projection distorts less.
    if extent_width_deg is not None and float(extent_width_deg) > 3.0:
        if float(extent_width_deg) > 6.0:
            return {
                "proj4": CHINA_ALBERS_PROJ4,
                "label": "China Albers Equal Area (lat_1=25, lat_2=47, lon_0=105)",
                "reason": "extent_wider_than_gauss_kruger_belt",
            }
        central = _gauss_kruger_cm(
            lon, _GK6_CM_STEP_DEG, _GK6_CM_MIN_DEG, _GK6_CM_MAX_DEG
        )
        offset = (central - _GK6_CM_MIN_DEG) // _GK6_CM_STEP_DEG
        return {
            "authid": f"EPSG:{_GK6_CM_BASE_EPSG + offset}",
            "label": f"CGCS2000 / Gauss-Kruger CM {central}E",
            "reason": "six_degree_belt_for_wide_extent",
        }

    central = _gauss_kruger_cm(
        lon, _GK3_CM_STEP_DEG, _GK3_CM_MIN_DEG, _GK3_CM_MAX_DEG
    )
    offset = (central - _GK3_CM_MIN_DEG) // _GK3_CM_STEP_DEG
    return {
        "authid": f"EPSG:{_GK3_CM_BASE_EPSG + offset}",
        "label": f"CGCS2000 / 3-degree Gauss-Kruger CM {central}E",
        "reason": "three_degree_belt_for_large_scale_terrain",
    }


def datum_advisory(*, center_lon, center_lat, dem_cell_size_m=None):
    """Describe the Chinese-datum hazard for an analysis centred here.

    Returns ``None`` outside the advisory area. The datum cannot be detected
    from the data — that is the whole problem — so this reports the size of the
    error a mix-up would cause and leaves the judgement to the user.
    """
    lon = float(center_lon)
    lat = float(center_lat)
    if not in_china_advisory_area(lon, lat):
        return None

    gcj_offset = gcj02_offset_meters(lon, lat)
    bd_offset = bd09_offset_meters(lon, lat)
    advisory = {
        "gcj02_offset_m": gcj_offset,
        "bd09_offset_m": bd_offset,
        "recommended_crs": recommended_projected_crs(lon, lat),
        "severity": "info",
        "cells_shifted": None,
    }

    try:
        cell_size = float(dem_cell_size_m) if dem_cell_size_m else 0.0
    except (TypeError, ValueError):
        cell_size = 0.0
    if cell_size > 0.0:
        cells = gcj_offset / cell_size
        advisory["cells_shifted"] = cells
        # One cell of slip already moves a ridge or channel reading onto a
        # different landform; ten makes the whole reading someone else's hill.
        advisory["severity"] = "critical" if cells >= 10.0 else "warning"
    return advisory
