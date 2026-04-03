# -*- coding: utf-8 -*-
"""Geometry and CRS helpers for analysis workflows."""

from __future__ import annotations

from qgis.core import (
    QgsCoordinateTransform,
    QgsFeature,
    QgsGeometry,
    QgsPointXY,
    QgsSpatialIndex,
)


def build_transform(source_crs, target_crs, project):
    if source_crs is None or target_crs is None:
        raise RuntimeError("Missing CRS required for coordinate transform.")
    if not source_crs.isValid() or not target_crs.isValid():
        raise RuntimeError("Invalid CRS encountered while preparing coordinate transform.")
    if source_crs == target_crs:
        return None
    try:
        return QgsCoordinateTransform(source_crs, target_crs, project)
    except (RuntimeError, TypeError, ValueError) as exc:
        raise RuntimeError(
            f"Failed to build coordinate transform: {source_crs.authid()} -> {target_crs.authid()}"
        ) from exc


def transform_point(point, transformer):
    if point is None:
        return None
    if transformer is None:
        return QgsPointXY(point.x(), point.y())
    try:
        transformed = transformer.transform(QgsPointXY(point.x(), point.y()))
        return QgsPointXY(transformed.x(), transformed.y())
    except (RuntimeError, TypeError, ValueError) as exc:
        raise RuntimeError("Failed to transform point geometry.") from exc


def transform_geometry(geometry, transformer):
    if geometry is None or geometry.isEmpty():
        return None
    cloned = QgsGeometry(geometry)
    if transformer is None:
        return cloned
    try:
        cloned.transform(transformer)
        return cloned
    except (RuntimeError, TypeError, ValueError) as exc:
        raise RuntimeError("Failed to transform feature geometry.") from exc


def geometry_point(geometry):
    if geometry is None or geometry.isEmpty():
        return None
    centroid = geometry.centroid()
    if centroid is None or centroid.isEmpty():
        return None
    point = centroid.asPoint()
    if point is None:
        return None
    return QgsPointXY(point.x(), point.y())


def feature_point(feature):
    if feature is None or not feature.hasGeometry():
        return None
    return geometry_point(feature.geometry())


def collect_points(*, layer, target_crs, project):
    points = []
    transformer = None
    if target_crs is not None and layer is not None and hasattr(layer, "crs"):
        transformer = build_transform(layer.crs(), target_crs, project)
    for feature in layer.getFeatures():
        point = feature_point(feature)
        point = transform_point(point, transformer)
        if point is not None:
            points.append(point)
    return points


def prepare_water_reference(*, dem_layer, water_layer, project):
    if dem_layer is None or water_layer is None:
        return None, None

    dem_crs = dem_layer.crs()
    water_to_dem = build_transform(water_layer.crs(), dem_crs, project)
    indexed_features = []
    transformed_geoms = {}
    for src_feature in water_layer.getFeatures():
        if not src_feature.hasGeometry():
            continue
        transformed = transform_geometry(
            src_feature.geometry(),
            water_to_dem,
        )
        if transformed is None or transformed.isEmpty():
            continue
        feature_id = int(src_feature.id())
        indexed = QgsFeature()
        indexed.setId(feature_id)
        indexed.setGeometry(transformed)
        indexed_features.append(indexed)
        transformed_geoms[feature_id] = transformed
    if not indexed_features:
        return None, None
    spatial_index = QgsSpatialIndex(QgsSpatialIndex.FlagStoreFeatureGeometries)
    for indexed_feature in indexed_features:
        spatial_index.addFeature(indexed_feature)
    return spatial_index, transformed_geoms
