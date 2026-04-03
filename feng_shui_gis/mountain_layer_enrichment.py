# -*- coding: utf-8 -*-
"""Helpers for enriching output layers with nearby mountain names."""

from __future__ import annotations

from qgis.PyQt.QtCore import QVariant
from qgis.core import QgsField, QgsProject, QgsVectorLayer, QgsWkbTypes, edit

from .mountain_enrichment import group_layers_by_crs
from .mountain_lookup import MountainNameService
from .mountain_options import mountain_options


def feature_anchor_point(feature):
    if feature is None or not feature.hasGeometry():
        return None
    geom = feature.geometry()
    if geom is None or geom.isEmpty():
        return None

    if geom.type() == QgsWkbTypes.PointGeometry:
        point = geom.asPoint()
        return point if point is not None else None

    centroid = geom.centroid()
    if centroid is not None and not centroid.isEmpty():
        point = centroid.asPoint()
        if point is not None:
            return point

    surface = geom.pointOnSurface()
    if surface is not None and not surface.isEmpty():
        point = surface.asPoint()
        if point is not None:
            return point
    return None


def feature_priority(feature, field_names):
    def _safe_int(value):
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _safe_float(value):
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    if "rank" in field_names:
        rank_value = _safe_int(feature["rank"])
        if rank_value is not None:
            return (0, rank_value, int(feature.id()))
    if "ridge_rank" in field_names:
        rank_value = _safe_int(feature["ridge_rank"])
        if rank_value is not None:
            return (1, rank_value, int(feature.id()))
    if "stream_id" in field_names:
        stream_id = _safe_int(feature["stream_id"])
        if stream_id is not None:
            return (2, stream_id, int(feature.id()))
    if "fs_score" in field_names:
        fs_score = _safe_float(feature["fs_score"])
        if fs_score is not None:
            return (3, -fs_score, int(feature.id()))
    return (9, int(feature.id()), 0)


def resolved_mountain_enrichment_options(
    *,
    radius_m=None,
    max_features=None,
    preferred_language=None,
):
    options = mountain_options()
    if radius_m is None:
        radius_m = options["radius_default_m"]
    if max_features is None:
        max_features = options["max_features_default"]
    if preferred_language is None:
        preferred_language = options["language_default"]
    if preferred_language not in ("local", "ko", "en"):
        preferred_language = options["language_default"]

    radius_m = max(
        int(options["radius_min_m"]),
        min(int(options["radius_max_m"]), int(radius_m)),
    )
    max_features = max(
        int(options["max_features_min"]),
        min(int(options["max_features_max"]), int(max_features)),
    )
    return {
        "radius_m": radius_m,
        "max_features": max_features,
        "preferred_language": preferred_language,
    }


def enrich_layer_with_mountain_names(
    layer,
    *,
    radius_m=None,
    max_features=None,
    preferred_language=None,
    service=None,
    candidates=None,
    project=None,
):
    if not isinstance(layer, QgsVectorLayer):
        return 0
    if layer.wkbType() == QgsWkbTypes.NoGeometry:
        return 0
    if layer.featureCount() <= 0:
        return 0

    resolved = resolved_mountain_enrichment_options(
        radius_m=radius_m,
        max_features=max_features,
        preferred_language=preferred_language,
    )
    radius_m = resolved["radius_m"]
    max_features = resolved["max_features"]
    preferred_language = resolved["preferred_language"]

    if service is None:
        service = MountainNameService(project=project or QgsProject.instance())
    if candidates is None:
        candidates = service.fetch_candidates_for_extent(layer.extent(), layer.crs())
    if not candidates:
        return 0

    field_names = {field.name() for field in layer.fields()}
    to_add = []
    if "mt_name" not in field_names:
        to_add.append(QgsField("mt_name", QVariant.String, "string", 96))
    if "mt_dist_m" not in field_names:
        to_add.append(QgsField("mt_dist_m", QVariant.Double, "double", 12, 1))
    if "mt_source" not in field_names:
        to_add.append(QgsField("mt_source", QVariant.String, "string", 24))
    if "mt_lang" not in field_names:
        to_add.append(QgsField("mt_lang", QVariant.String, "string", 10))
    if to_add:
        layer.dataProvider().addAttributes(to_add)
        layer.updateFields()
        field_names = {field.name() for field in layer.fields()}

    features = [feature for feature in layer.getFeatures() if feature.hasGeometry()]
    features.sort(key=lambda feature: feature_priority(feature, field_names))
    selected = features[: max(1, int(max_features))]

    updated = 0
    with edit(layer):
        for feature in selected:
            point = feature_anchor_point(feature)
            nearest = service.nearest_name(
                point=point,
                source_crs=layer.crs(),
                candidates=candidates,
                max_distance_m=radius_m,
                preferred_language=preferred_language,
            )
            if nearest is None:
                continue
            feature["mt_name"] = nearest.get("name")
            feature["mt_dist_m"] = nearest.get("distance_m")
            feature["mt_source"] = nearest.get("source")
            feature["mt_lang"] = nearest.get("name_language")
            layer.updateFeature(feature)
            updated += 1
    return updated


def enrich_layers_with_mountain_names(
    layers,
    *,
    radius_m=None,
    max_features=None,
    preferred_language=None,
    project=None,
    warn_lookup_status=None,
):
    def _is_valid_layer(layer):
        if not isinstance(layer, QgsVectorLayer):
            return False
        if layer.wkbType() == QgsWkbTypes.NoGeometry:
            return False
        return layer.featureCount() > 0

    def _crs_key_for_layer(layer):
        crs = layer.crs()
        crs_key = crs.authid() if crs is not None and crs.isValid() else str(id(layer))
        return crs_key, crs

    grouped_layers = group_layers_by_crs(
        layers,
        is_valid_layer=_is_valid_layer,
        crs_key_for_layer=_crs_key_for_layer,
    )
    if not grouped_layers:
        return 0

    service = MountainNameService(project=project or QgsProject.instance())
    total_updated = 0
    lookup_warning_emitted = False
    for group in grouped_layers:
        group_layers = group["layers"]
        combined_extent = None
        for layer in group_layers:
            extent = layer.extent()
            if extent is None or extent.isEmpty():
                continue
            if combined_extent is None:
                combined_extent = layer.extent()
            else:
                combined_extent.combineExtentWith(extent)

        group_candidates = None
        if combined_extent is not None and not combined_extent.isEmpty():
            group_candidates = service.fetch_candidates_for_extent(
                combined_extent,
                group["crs"],
            )
            if (
                not group_candidates
                and not lookup_warning_emitted
                and warn_lookup_status is not None
            ):
                lookup_warning_emitted = bool(warn_lookup_status(service))
        shared_candidates = group_candidates if group_candidates else None

        for layer in group_layers:
            total_updated += enrich_layer_with_mountain_names(
                layer,
                radius_m=radius_m,
                max_features=max_features,
                preferred_language=preferred_language,
                service=service,
                candidates=shared_candidates,
                project=project,
            )
    return total_updated
