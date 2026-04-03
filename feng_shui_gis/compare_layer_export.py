# -*- coding: utf-8 -*-
"""Helpers for compare-layer export and styling."""

from __future__ import annotations

from qgis.PyQt.QtCore import QVariant
from qgis.PyQt.QtGui import QColor
from qgis.core import (
    QgsCategorizedSymbolRenderer,
    QgsFeature,
    QgsFeatureRequest,
    QgsField,
    QgsRendererCategory,
    QgsSymbol,
    QgsVectorLayer,
    QgsWkbTypes,
)

from .feature_identity import feature_uid, uid_match_summary
from .ui_catalog import ui_text


def _reason_excerpt(text, limit):
    clean = str(text or "").strip().replace("\n", " ")
    limit = max(1, int(limit))
    if len(clean) <= limit:
        return clean
    return clean[: limit - 1].rstrip() + "…"


def compare_trend(delta_value, epsilon=0.01):
    delta_value = float(delta_value)
    if delta_value > float(epsilon):
        return "gain"
    if delta_value < (-float(epsilon)):
        return "drop"
    return "neutral"


def export_top_changed_features_layer(
    *,
    compare_layer,
    top_changes,
    compare_profile_key,
    label_lang,
    output_layer_name,
    compare_delta_epsilon=0.01,
    reason_excerpt_limit=96,
):
    if compare_layer is None or not top_changes:
        return None

    feature_map = {}
    for row in top_changes:
        if not isinstance(row, dict):
            continue
        feature_uid_value = row.get("feature_uid")
        if not feature_uid_value:
            continue
        feature_map[str(feature_uid_value)] = row
    if not feature_map:
        return None

    geometry_name = QgsWkbTypes.displayString(compare_layer.wkbType()) or "Point"
    crs_authid = compare_layer.crs().authid() or "EPSG:4326"
    export_layer = QgsVectorLayer(
        f"{geometry_name}?crs={crs_authid}",
        output_layer_name,
        "memory",
    )
    if not export_layer.isValid():
        return None

    provider = export_layer.dataProvider()
    provider.addAttributes(list(compare_layer.fields()))
    provider.addAttributes(
        [
            QgsField("cmp_label", QVariant.String, "string", 120),
            QgsField("cmp_base", QVariant.Double, "double", 7, 4),
            QgsField("cmp_score", QVariant.Double, "double", 7, 4),
            QgsField("cmp_delta", QVariant.Double, "double", 7, 4),
            QgsField("cmp_trend", QVariant.String, "string", 16),
            QgsField("cmp_reason_b", QVariant.String, "string", 1024),
            QgsField("cmp_reason_c", QVariant.String, "string", 1024),
            QgsField("cmp_feature_uid", QVariant.String, "string", 128),
            QgsField("cmp_model", QVariant.String, "string", 80),
        ]
    )
    export_layer.updateFields()

    output_fields = export_layer.fields()
    original_field_names = compare_layer.fields().names()
    requested_uids = [str(uid_value) for uid_value in feature_map.keys()]
    requested_summary = uid_match_summary(
        compare_layer,
        requested_uids,
        field_names=original_field_names,
    )
    requested_fids = requested_summary["feature_ids"]
    if requested_summary["missing"] or requested_summary["ambiguous"] or not requested_fids:
        return None

    new_features = []
    for source_feature in compare_layer.getFeatures(
        QgsFeatureRequest().setFilterFids(requested_fids)
    ):
        source_uid = feature_uid(source_feature, field_names=original_field_names)
        row = feature_map.get(str(source_uid))
        if row is None:
            continue
        new_feature = QgsFeature(output_fields)
        new_feature.setGeometry(source_feature.geometry())
        for field_name in original_field_names:
            try:
                new_feature[field_name] = source_feature[field_name]
            except (KeyError, TypeError, ValueError):
                continue
        new_feature["cmp_label"] = str(row.get("label", ""))
        new_feature["cmp_base"] = float(row.get("base_score", 0.0))
        new_feature["cmp_score"] = float(row.get("compare_score", 0.0))
        new_feature["cmp_delta"] = float(row.get("delta", 0.0))
        base_reason = str(row.get("base_reason", "") or "")
        compare_reason = str(row.get("compare_reason", "") or "")
        new_feature["cmp_trend"] = compare_trend(
            row.get("delta", 0.0),
            epsilon=compare_delta_epsilon,
        )
        new_feature["cmp_reason_b"] = base_reason
        new_feature["cmp_reason_c"] = compare_reason
        if "fs_reason" in original_field_names:
            if label_lang == "ko":
                reason_summary = (
                    f"[기준] {_reason_excerpt(base_reason, reason_excerpt_limit)} | "
                    f"[보정] {_reason_excerpt(compare_reason, reason_excerpt_limit)}"
                )
            else:
                reason_summary = (
                    f"[Base] {_reason_excerpt(base_reason, reason_excerpt_limit)} | "
                    f"[Calibrated] {_reason_excerpt(compare_reason, reason_excerpt_limit)}"
                )
            new_feature["fs_reason"] = reason_summary
        new_feature["cmp_feature_uid"] = str(source_uid)
        new_feature["cmp_model"] = str(compare_profile_key)
        new_features.append(new_feature)

    if not new_features or len(new_features) != len(feature_map):
        return None
    provider.addFeatures(new_features)
    export_layer.updateExtents()
    return export_layer


def style_compare_change_layer(layer, trend_styles, label_lang):
    if layer is None or not isinstance(layer, QgsVectorLayer):
        return
    categories = []
    for value, color_hex, label_key, default_label in trend_styles:
        symbol = QgsSymbol.defaultSymbol(layer.geometryType())
        if symbol is None:
            continue
        symbol.setColor(QColor(color_hex))
        symbol.setOpacity(0.88)
        try:
            symbol.setWidth(0.9)
        except (AttributeError, TypeError, RuntimeError):
            pass
        try:
            symbol.setSize(4.6)
        except (AttributeError, TypeError, RuntimeError):
            pass
        categories.append(
            QgsRendererCategory(
                value,
                symbol,
                ui_text(label_key, label_lang, default=default_label),
            )
        )
    if not categories:
        return
    layer.setRenderer(QgsCategorizedSymbolRenderer("cmp_trend", categories))
    layer.triggerRepaint()
