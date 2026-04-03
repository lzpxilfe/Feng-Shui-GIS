# -*- coding: utf-8 -*-
"""Term-layer assembly helpers for terrain interpretation outputs."""

from __future__ import annotations

from qgis.PyQt.QtCore import QVariant
from qgis.core import QgsFeature, QgsField, QgsFields, QgsGeometry


def term_layer_fields():
    fields = QgsFields()
    fields.append(QgsField("term_id", QVariant.String, "string", 28))
    fields.append(QgsField("term_ko", QVariant.String, "string", 28))
    fields.append(QgsField("term_name", QVariant.String, "string", 28))
    fields.append(QgsField("culture", QVariant.String, "string", 20))
    fields.append(QgsField("period", QVariant.String, "string", 20))
    fields.append(QgsField("profile", QVariant.String, "string", 20))
    fields.append(QgsField("parent_id", QVariant.Int))
    fields.append(QgsField("rank", QVariant.Int))
    fields.append(QgsField("score", QVariant.Double, "double", 7, 3))
    fields.append(QgsField("elev", QVariant.Double, "double", 12, 3))
    fields.append(QgsField("base_sc", QVariant.Double, "double", 7, 3))
    fields.append(QgsField("delta_rel", QVariant.Double, "double", 8, 4))
    fields.append(QgsField("target_rel", QVariant.Double, "double", 8, 4))
    fields.append(QgsField("fit_sc", QVariant.Double, "double", 7, 3))
    fields.append(QgsField("radius_m", QVariant.Double, "double", 12, 3))
    fields.append(QgsField("azimuth", QVariant.Double, "double", 7, 2))
    fields.append(QgsField("mode", QVariant.String, "string", 8))
    fields.append(QgsField("relief_m", QVariant.Double, "double", 12, 3))
    fields.append(QgsField("note", QVariant.String, "string", 80))
    fields.append(QgsField("reason_ko", QVariant.String, "string", 1024))
    return fields


def term_runtime_state(
    *,
    context,
    profile,
    dem_step,
    scales,
    min_score_floor,
    threshold_multiplier,
):
    culture_id = context["culture_key"]
    period_id = context["period_key"]
    term_bias = dict(context.get("term_bias", {}))
    if not isinstance(profile, dict):
        profile = {}
    profile_term_bias = profile.get("term_bias", {})
    if not isinstance(profile_term_bias, dict):
        profile_term_bias = {}
    for term_id, delta in profile_term_bias.items():
        term_bias[term_id] = term_bias.get(term_id, 0.0) + delta

    radius_map = {
        "inner": dem_step * float(scales["inner"]) * float(context["micro_radius_multiplier"]),
        "outer": dem_step * float(scales["outer"]) * float(context["macro_radius_multiplier"]),
        "far": dem_step * float(scales["far"]) * float(context["macro_radius_multiplier"]),
    }
    term_min_score = max(
        min_score_floor,
        float(context["hyeol_threshold"]) * threshold_multiplier,
    )
    return {
        "culture_id": culture_id,
        "period_id": period_id,
        "term_bias": term_bias,
        "term_target_shift": float(context["term_target_shift"]),
        "term_min_score": term_min_score,
        "radius_map": radius_map,
    }


def adjusted_term_score(score, *, term_id, term_bias, term_min_score, mandatory=False):
    adjusted_score = score
    if adjusted_score is not None:
        adjusted_score = max(
            0.0,
            min(1.0, adjusted_score + term_bias.get(term_id, 0.0)),
        )
    if not mandatory and adjusted_score is not None and adjusted_score < term_min_score:
        return None
    return adjusted_score


def append_term_feature(
    layer,
    *,
    term_id,
    term_name,
    parent_id,
    rank,
    point,
    score,
    elev,
    note,
    base_sc=None,
    delta_rel=None,
    target_rel=None,
    fit_sc=None,
    radius_m=None,
    azimuth=None,
    mode=None,
    relief_m=None,
    term_ko=None,
    culture=None,
    period=None,
    profile=None,
    reason_ko=None,
):
    feature = QgsFeature(layer.fields())
    feature.setGeometry(QgsGeometry.fromPointXY(point))
    feature["term_id"] = term_id
    feature["term_ko"] = term_ko if term_ko else term_id
    feature["term_name"] = term_name
    feature["culture"] = culture if culture else ""
    feature["period"] = period if period else ""
    feature["profile"] = profile if profile else ""
    feature["parent_id"] = parent_id
    feature["rank"] = rank
    feature["score"] = score
    feature["elev"] = elev
    feature["base_sc"] = base_sc
    feature["delta_rel"] = delta_rel
    feature["target_rel"] = target_rel
    feature["fit_sc"] = fit_sc
    feature["radius_m"] = radius_m
    feature["azimuth"] = azimuth
    feature["mode"] = mode if mode else ""
    feature["relief_m"] = relief_m
    feature["note"] = note
    feature["reason_ko"] = reason_ko if reason_ko else ""
    layer.dataProvider().addFeature(feature)

