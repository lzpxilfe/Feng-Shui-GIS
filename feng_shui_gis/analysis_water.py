# -*- coding: utf-8 -*-
"""Water and DEM-distance helpers for analysis workflows."""

from __future__ import annotations


def dem_step(dem_layer):
    x_res = abs(dem_layer.rasterUnitsPerPixelX())
    y_res = abs(dem_layer.rasterUnitsPerPixelY())
    step = max(x_res, y_res)
    return step if step > 0 else 1.0


def nearest_water_distance(site_geom, site_point, water_index, water_geoms):
    if (
        site_geom is None
        or site_geom.isEmpty()
        or site_point is None
        or water_index is None
        or not water_geoms
    ):
        return None

    try:
        candidate_ids = water_index.nearestNeighbor(site_geom, 12)
    except TypeError:
        candidate_ids = water_index.nearestNeighbor(site_point, 12)
    if not candidate_ids:
        return None

    best = None
    for fid in candidate_ids:
        water_geom = water_geoms.get(fid)
        if water_geom is None:
            continue
        distance = site_geom.distance(water_geom)
        if best is None or distance < best:
            best = distance
    return best
