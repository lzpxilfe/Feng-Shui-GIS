# -*- coding: utf-8 -*-
"""Helpers for term-link layer assembly."""

from __future__ import annotations

from collections import defaultdict
import math

from qgis.PyQt.QtCore import QVariant
from qgis.core import QgsFeature, QgsField, QgsFields, QgsGeometry, QgsPointXY


def term_link_fields():
    fields = QgsFields()
    fields.append(QgsField("term_id", QVariant.String, "string", 28))
    fields.append(QgsField("term_ko", QVariant.String, "string", 28))
    fields.append(QgsField("term_en", QVariant.String, "string", 28))
    fields.append(QgsField("term_lbl", QVariant.String, "string", 28))
    fields.append(QgsField("parent_id", QVariant.Int))
    fields.append(QgsField("rank", QVariant.Int))
    fields.append(QgsField("score", QVariant.Double, "double", 7, 3))
    fields.append(QgsField("culture", QVariant.String, "string", 20))
    fields.append(QgsField("period", QVariant.String, "string", 20))
    fields.append(QgsField("profile", QVariant.String, "string", 20))
    fields.append(QgsField("src_id", QVariant.String, "string", 28))
    fields.append(QgsField("src_ko", QVariant.String, "string", 28))
    fields.append(QgsField("src_en", QVariant.String, "string", 28))
    fields.append(QgsField("src_lbl", QVariant.String, "string", 28))
    fields.append(QgsField("dst_id", QVariant.String, "string", 28))
    fields.append(QgsField("dst_ko", QVariant.String, "string", 28))
    fields.append(QgsField("dst_en", QVariant.String, "string", 28))
    fields.append(QgsField("dst_lbl", QVariant.String, "string", 28))
    fields.append(QgsField("link_type", QVariant.String, "string", 20))
    fields.append(QgsField("len_m", QVariant.Double, "double", 12, 3))
    fields.append(QgsField("azimuth", QVariant.Double, "double", 7, 2))
    fields.append(QgsField("curved", QVariant.Int))
    fields.append(QgsField("reason_ko", QVariant.String, "string", 1024))
    return fields


def group_term_features(features):
    grouped = defaultdict(dict)
    for feature in features:
        term_id = feature["term_id"]
        parent_id = feature["parent_id"]
        if not term_id or parent_id is None:
            continue
        if not feature.hasGeometry():
            continue
        grouped[parent_id][term_id] = feature
    return grouped


def build_term_link_reason(
    *,
    spec_label,
    source_id,
    target_id,
    style_term,
    score,
    length_m,
    azimuth,
    azimuth_label,
    term_label_ko,
):
    score_text = "n/a" if score is None else f"{score:.3f}"
    return (
        f"{spec_label} 경로 {term_label_ko(source_id)}→{term_label_ko(target_id)}. "
        f"표현={term_label_ko(style_term)}, 형태=완만 곡선, 평균점수={score_text}, "
        f"거리={length_m:.1f}m, 방위={azimuth:.1f}°({azimuth_label(azimuth)}), "
        "명당 중심 방사 연결 대신 감싸는 구조를 우선 적용."
    )


def build_term_link_feature(
    *,
    fields,
    smoothed_points,
    parent_id,
    rank_value,
    score,
    source,
    target,
    spec,
    length_m,
    azimuth,
    azimuth_label,
    term_label,
    term_label_ko,
    label_language="ko",
):
    source_id = source["term_id"]
    target_id = target["term_id"]
    style_term = spec["style_term"]

    feature = QgsFeature(fields)
    feature.setGeometry(QgsGeometry.fromPolylineXY(smoothed_points))
    feature["term_id"] = style_term
    feature["term_ko"] = term_label_ko(style_term)
    feature["term_en"] = term_label(style_term, "en")
    feature["term_lbl"] = term_label(style_term, label_language)
    feature["parent_id"] = parent_id
    feature["rank"] = rank_value
    feature["score"] = score
    feature["culture"] = source["culture"] or target["culture"]
    feature["period"] = source["period"] or target["period"]
    feature["profile"] = source["profile"] or target["profile"]
    feature["src_id"] = source_id
    feature["src_ko"] = term_label_ko(source_id)
    feature["src_en"] = term_label(source_id, "en")
    feature["src_lbl"] = term_label(source_id, label_language)
    feature["dst_id"] = target_id
    feature["dst_ko"] = term_label_ko(target_id)
    feature["dst_en"] = term_label(target_id, "en")
    feature["dst_lbl"] = term_label(target_id, label_language)
    feature["link_type"] = spec["link_type"]
    feature["len_m"] = length_m
    feature["azimuth"] = azimuth
    feature["curved"] = 1
    feature["reason_ko"] = build_term_link_reason(
        spec_label=spec.get("label_ko", spec["label"]),
        source_id=source_id,
        target_id=target_id,
        style_term=style_term,
        score=score,
        length_m=length_m,
        azimuth=azimuth,
        azimuth_label=azimuth_label,
        term_label_ko=term_label_ko,
    )
    return feature


def path_mean_score(features, to_float):
    values = []
    for feature in features:
        value = to_float(feature["score"])
        if value is not None:
            values.append(value)
    if not values:
        return None
    return sum(values) / len(values)


def polyline_length(points):
    length = 0.0
    for idx in range(1, len(points)):
        prev = points[idx - 1]
        curr = points[idx]
        length += math.hypot(curr.x() - prev.x(), curr.y() - prev.y())
    return length


def distinct_points(points, min_distance=0.1):
    if not points:
        return []
    clean = [QgsPointXY(points[0].x(), points[0].y())]
    min_sq = max(1e-6, float(min_distance) * float(min_distance))
    for point in points[1:]:
        prev = clean[-1]
        dx = point.x() - prev.x()
        dy = point.y() - prev.y()
        if (dx * dx) + (dy * dy) < min_sq:
            continue
        clean.append(QgsPointXY(point.x(), point.y()))
    if len(clean) == 1 and len(points) > 1:
        tail = points[-1]
        clean.append(QgsPointXY(tail.x(), tail.y()))
    return clean


def smooth_polyline(points, passes=1):
    if len(points) < 3 or passes <= 0:
        return [QgsPointXY(point.x(), point.y()) for point in points]

    current = [QgsPointXY(point.x(), point.y()) for point in points]
    for _ in range(passes):
        if len(current) < 3:
            break
        smoothed = [QgsPointXY(current[0].x(), current[0].y())]
        for idx in range(len(current) - 1):
            point_a = current[idx]
            point_b = current[idx + 1]
            qx = (0.75 * point_a.x()) + (0.25 * point_b.x())
            qy = (0.75 * point_a.y()) + (0.25 * point_b.y())
            rx = (0.25 * point_a.x()) + (0.75 * point_b.x())
            ry = (0.25 * point_a.y()) + (0.75 * point_b.y())
            smoothed.append(QgsPointXY(qx, qy))
            smoothed.append(QgsPointXY(rx, ry))
        smoothed.append(QgsPointXY(current[-1].x(), current[-1].y()))
        current = smoothed
    return current


def link_ready_payload(
    nodes,
    points,
    *,
    spec,
    min_link_score,
    distinct_min_distance,
    smooth_passes,
    to_float,
):
    clean_points = distinct_points(points, min_distance=distinct_min_distance)
    if len(clean_points) < 2:
        return None

    smoothed_points = smooth_polyline(clean_points, passes=smooth_passes)
    if len(smoothed_points) < 2:
        return None

    score = path_mean_score(nodes, to_float)
    if score is not None and score < min_link_score and spec["link_type"] != "backbone":
        return None

    length_m = polyline_length(smoothed_points)
    if length_m <= 0:
        return None

    origin = smoothed_points[0]
    destination = smoothed_points[-1]
    dx = destination.x() - origin.x()
    dy = destination.y() - origin.y()
    azimuth = (math.degrees(math.atan2(dx, dy)) + 360.0) % 360.0
    source = nodes[0]
    target = nodes[-1]
    rank_value = source["rank"] if source["rank"] is not None else target["rank"]
    return {
        "source": source,
        "target": target,
        "score": score,
        "rank_value": rank_value,
        "smoothed_points": smoothed_points,
        "length_m": length_m,
        "azimuth": azimuth,
    }
